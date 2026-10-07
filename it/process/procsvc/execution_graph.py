"""Version-scoped execution projection over HYD's BPMN knowledge schema.

ProcessGPT retains head elements and records dangling historical references.
HYD retains immutable version elements too, so changed-definition exercises can
compare their execution history. Relational definitions remain authoritative.
"""
from urllib.parse import quote
from .engine import _properties


def scoped(kind, *parts):
    return kind + ':' + ':'.join(quote(str(p), safe='') for p in parts)


def definition_projection(defn, tenant):
    version = defn.raw['version']
    version_id = scoped('proc-version', tenant, defn.id, version)
    def node_id(local):
        return scoped('flow', tenant, defn.id, version, local)
    nodes = []
    for label, values in (('Task', defn.activities.values()), ('Event', defn.events.values()), ('Gateway', defn.gateways.values())):
        for raw in values:
            props = {'name': raw.get('name') or raw['id'], 'tenant_id': tenant, 'definition_id': defn.id,
                     'version': version, 'element_id': raw['id'], 'source_type': raw['type']}
            if label == 'Task':
                props.update(taskType=raw['type'].removesuffix('Task'), tool=raw.get('tool'))
                mode = str(raw.get('agentMode') or '').upper()        # A116: the product's Activity.agent_mode
                if mode in ('DRAFT', 'COMPLETE'):
                    props.update(agentMode=mode, orchestration=raw.get('orchestration'))
            elif label == 'Event':
                props.update(position={'startEvent': 'start', 'endEvent': 'end', 'boundaryEvent': 'boundary'}[raw['type']],
                             eventDefinition=raw.get('eventDefinition', 'none'), timer=raw.get('timer'),
                             messageRef=raw.get('messageRef'), correlationKey=raw.get('correlationKey'))
            else:
                props['gatewayType'] = raw['type'].removesuffix('Gateway')
            nodes.append({'id': node_id(raw['id']), 'label': label, 'props': props,
                          'semantic_id': raw.get('ontologyRef') or raw['id']})
    flows = [{'source': node_id(s['source']), 'target': node_id(s['target']),
              'id': s['id'], 'condition': s.get('condition'), 'priority': _properties(s).get('priority'),
              'isDefault': _properties(s).get('default') is True} for s in defn.sequences]
    return {'definition_id': defn.id, 'definition_name': defn.name, 'version_id': version_id,
            'nodes': nodes, 'flows': flows}, node_id


# The fence survives graph deletion so a delayed pre-delete write cannot resurrect
# source data. SET dependency acquires Neo4j's write lock before comparing revision.
FENCE_Q = '''
MERGE (f:ExecutionProjection {id:$id})
SET f.lock = coalesce(f.lock,0)+1
WITH f WHERE coalesce(f.revision,0)<$revision OR (f.revision=$revision AND f.payload_hash=$payload_hash)
SET f.revision=$revision, f.tenant_id=$tenant,f.payload_hash=$payload_hash
WITH f
'''

DELETE_INSTANCE_Q = FENCE_Q + '''
OPTIONAL MATCH (pi:ProcessInstance {id:$id})
OPTIONAL MATCH (w:WorkItem)-[:IN_INSTANCE]->(pi)
DETACH DELETE w,pi
RETURN $id AS projection_key,$revision AS projection_revision,$payload_hash AS projection_hash
'''

INSTANCE_Q = FENCE_Q + '''
MERGE (pv:ProcessVersion {id:$version_id})
SET pv.name=$definition_name, pv.definition_id=$definition_id, pv.version=$version, pv.tenant_id=$tenant,
    pv.ontology_ref=$process
WITH pv
CALL (pv) {
  UNWIND $nodes AS item
  MERGE (n:FlowNode {id:item.id}) SET n += item.props
  FOREACH (_ IN CASE WHEN item.label='Task' THEN [1] ELSE [] END | SET n:Task)
  FOREACH (_ IN CASE WHEN item.label='Event' THEN [1] ELSE [] END | SET n:Event)
  FOREACH (_ IN CASE WHEN item.label='Gateway' THEN [1] ELSE [] END | SET n:Gateway)
  MERGE (pv)-[:HAS_NODE]->(n)
  WITH n,item
  CALL (n) { OPTIONAL MATCH (n)-[old:MAPS_TO]->() DELETE old RETURN count(*) AS removed }
  OPTIONAL MATCH (:Process {id:$process})-[:HAS_NODE]->(semantic:FlowNode {id:item.semantic_id})
  SET n.semantic_id=item.semantic_id,
      n.semantic_warning=CASE WHEN semantic IS NULL AND $process IS NOT NULL THEN 'ontology flow mapping missing: '+item.props.element_id ELSE null END
  FOREACH (_ IN CASE WHEN semantic IS NULL THEN [] ELSE [1] END | MERGE (n)-[:MAPS_TO]->(semantic))
  RETURN count(*) AS definition_nodes,collect(n.semantic_warning) AS mapping_warnings
}
SET pv.projection_warnings=mapping_warnings
WITH pv
CALL (pv) {
  UNWIND $flows AS flow
  MATCH (a:FlowNode {id:flow.source})
  WITH flow,a
  MATCH (b:FlowNode {id:flow.target})
  MERGE (a)-[r:SEQUENCE_FLOW {id:flow.id}]->(b)
  SET r.condition=flow.condition, r.priority=flow.priority, r.isDefault=flow.isDefault
  RETURN count(*) AS definition_flows
}
MERGE (pi:ProcessInstance {id:$id})
SET pi.name=$name, pi.status=$status, pi.start_date=$start, pi.end_date=$end, pi.end_event=$end_event,
    pi.current_activity_ids=$current, pi.version=$version, pi.tenant_id=$tenant, pi.definition_id=$definition_id,
    pi.rework_generation=$generation, pi.projection_revision=$revision
MERGE (pi)-[:USES_VERSION]->(pv)
WITH pi,pv
CALL (pi) {
  OPTIONAL MATCH (pi)-[old:ON_ASSET|HANDLES]->() DELETE old
  RETURN count(*) AS removed_source_links
}
CALL (pi) {
  MATCH (old:WorkItem)-[:IN_INSTANCE]->(pi)
  WHERE NOT old.id IN [it IN $items | it.id]
  DETACH DELETE old
  RETURN count(*) AS removed_items
}
OPTIONAL MATCH (p:Process {id:$process})
SET pi.projection_warnings=(CASE WHEN p IS NULL AND $process IS NOT NULL THEN ['ontology process missing: '+$process] ELSE [] END)+coalesce(pv.projection_warnings,[])
WITH pi,pv,p
CALL (pi,p) {
  OPTIONAL MATCH (pi)-[old:INSTANCE_OF]->() DELETE old
  FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END | MERGE (pi)-[r:INSTANCE_OF]->(p) SET r.version=$version)
  RETURN count(*) AS process_links
}
CALL (pi) {
  OPTIONAL MATCH (pi)-[old:ROLE_BOUND]->() DELETE old
  RETURN count(*) AS removed_bindings
}
CALL (pi) {
  UNWIND $bindings AS b
  OPTIONAL MATCH (who {id:b.endpoint}) WHERE who:Role OR who:System
  FOREACH (_ IN CASE WHEN who IS NULL THEN [] ELSE [1] END |
    MERGE (pi)-[rb:ROLE_BOUND {role_name:b.role}]->(who))
  FOREACH (_ IN CASE WHEN who IS NULL THEN [1] ELSE [] END |
    SET pi.projection_warnings=pi.projection_warnings+['role endpoint missing: '+coalesce(b.endpoint,'null')])
  RETURN count(*) AS role_links
}
WITH pi,pv
OPTIONAL MATCH (a:Asset {code:$asset})
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END | MERGE (pi)-[:ON_ASSET]->(a))
WITH pi,pv OPTIONAL MATCH (i:Incident {id:$incident})
FOREACH (_ IN CASE WHEN i IS NULL THEN [] ELSE [1] END | MERGE (pi)-[:HANDLES]->(i))
FOREACH (_ IN CASE WHEN i IS NULL AND $incident IS NOT NULL THEN [1] ELSE [] END |
  SET pi.projection_warnings=pi.projection_warnings+['incident source not projected: '+$incident])
WITH pi,pv
CALL (pi,pv) {
  UNWIND $items AS it
  MERGE (w:WorkItem {id:it.id})
  SET w.activity_id=it.activity, w.activity_name=it.name, w.status=it.status, w.tool=it.tool, w.agent_mode=it.agent_mode,
      w.agent_orch=it.orch, w.draft_status=it.draft_status, w.retry=it.retry, w.rework_count=it.rework, w.duration=it.duration,
      w.start_date=it.start, w.end_date=it.end, w.due_date=it.due, w.tenant_id=$tenant,
      w.definition_id=$definition_id, w.version=$version, w.generation=it.generation,
      w.rework_request_id=it.request_id, w.supersedes_id=it.supersedes
  MERGE (w)-[:IN_INSTANCE]->(pi)
  WITH pi,w,it
  OPTIONAL MATCH (w)-[old:EXECUTES|ASSIGNED_TO]->() DELETE old
  WITH DISTINCT pi,w,it
  OPTIONAL MATCH (t:FlowNode {id:it.target})
  FOREACH (_ IN CASE WHEN t IS NULL THEN [] ELSE [1] END | MERGE (w)-[:EXECUTES]->(t))
  FOREACH (_ IN CASE WHEN t IS NULL THEN [1] ELSE [] END |
    SET pi.projection_warnings=pi.projection_warnings+['definition element missing: '+it.activity])
  WITH pi,w,it
  OPTIONAL MATCH (who {id:it.performer}) WHERE who:Role OR who:System
  FOREACH (_ IN CASE WHEN who IS NULL THEN [] ELSE [1] END |
    MERGE (w)-[ra:ASSIGNED_TO]->(who) SET ra.kind='single')
  FOREACH (_ IN CASE WHEN who IS NULL AND it.performer IS NOT NULL THEN [1] ELSE [] END |
    SET pi.projection_warnings=pi.projection_warnings+['performer missing: '+it.performer])
  RETURN count(*) AS projected_items
}
RETURN pi.id AS instance, projected_items,$id AS projection_key,$revision AS projection_revision,$payload_hash AS projection_hash
'''


EXECUTION_Q = '''
MATCH (pi:ProcessInstance {id: $id})
OPTIONAL MATCH (pi)-[io:INSTANCE_OF]->(p:Process)
OPTIONAL MATCH (pi)-[:USES_VERSION]->(pv:ProcessVersion)
OPTIONAL MATCH (pi)-[:ON_ASSET]->(a:Asset)
OPTIONAL MATCH (pi)-[:HANDLES]->(i:Incident)
OPTIONAL MATCH (pi)-[rb:ROLE_BOUND]->(who)
WITH pi,p,pv,io,a,i,collect(DISTINCT CASE WHEN who IS NULL THEN NULL ELSE
  {role_name:rb.role_name,endpoint:who.id,kind:labels(who)[0]} END) AS bindings
OPTIONAL MATCH (w:WorkItem)-[:IN_INSTANCE]->(pi)
OPTIONAL MATCH (w)-[:EXECUTES]->(t)
OPTIONAL MATCH (w)-[ra:ASSIGNED_TO]->(perf)
WITH pi,p,pv,io,a,i,bindings,w,t,ra,perf ORDER BY w.start_date,w.id
RETURN pi{.*} AS instance, p.id AS process, coalesce(pv.name,p.name) AS process_name,
       coalesce(pv.version,io.version) AS version, pv.id AS version_node, pv.definition_id AS definition_id,
       a.code AS asset, i.id AS incident, bindings,
       coalesce(pi.projection_warnings,[])+CASE WHEN pv IS NULL THEN ['version snapshot not projected'] ELSE [] END AS warnings,
       collect(CASE WHEN w IS NULL THEN NULL ELSE {workitem:w{.*},task:t.id,task_name:t.name,
         task_type:head([label IN labels(t) WHERE label <> 'FlowNode']),
         performer:perf.id,performer_kind:ra.kind} END) AS items
'''
