-- Upgrade only the known classroom Neo4j stdio definition. Preserve tenant tools,
-- secrets, endpoints and user-supplied custom Neo4j commands.
update public.tenants
set mcp = jsonb_set(jsonb_set(mcp, '{mcpServers,neo4j,command}', '"python"'::jsonb),
                    '{mcpServers,neo4j,args}', '["-m","hydcommon.neo4j_mcp"]'::jsonb)
where id = 'hyd'
  and mcp #>> '{mcpServers,neo4j,command}' = 'uvx'
  and mcp #> '{mcpServers,neo4j,args}' in (
      '["mcp-neo4j-cypher@0.4.1","--transport","stdio"]'::jsonb,
      '["--with","fastmcp==2.13.0.2","mcp-neo4j-cypher@0.4.1","--transport","stdio"]'::jsonb);
