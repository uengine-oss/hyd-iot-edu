CREATE CONSTRAINT lab_sensor_tag_exists IF NOT EXISTS FOR (n:Sensor) REQUIRE n.tag IS NOT NULL;
