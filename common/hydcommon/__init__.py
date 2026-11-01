"""hydcommon: the code every hyd-iot-edu service shares — topic names and payload contracts (topics · schemas · daq_contract),
service plumbing (service · metrics · mqtt · kafka · graphdb · timeutil), the plant model (plant_model · forecast) and the
decision domain rules (ranking · bsc · skill_scope · maintenance_* · execution_scope · purchase_comparison · fabric …).
Every service image copies the whole package; a module is imported only by the services that use it (OT/DMZ images do not
install the database drivers the decision modules import)."""
