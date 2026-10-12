MATCH (s:Sensor {id: 'sen:ts1'}) SET s.name = '오일 온도계' RETURN s.id, s.name;
