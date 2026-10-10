-- 연습용 DB: 센서가 보낸 값. 가장 늦은 시각의 값이 "현재 값"이다.
create table tags (
    tag         text primary key,          -- DB 에서 센서를 부르는 이름 (그래프 Sensor.tag 와 같다)
    asset_id    text not null,             -- 설비 번호
    description text not null
);

create table readings (
    tag         text not null references tags(tag),
    measured_at timestamptz not null,
    value       numeric not null,
    primary key (tag, measured_at)
);

insert into tags (tag, asset_id, description) values
    ('CL01_TT_OUT', 'CL-01', 'CHILLER A1 OUT TEMP'),
    ('CL01_FT',     'CL-01', 'CHILLER A1 FLOW'),
    ('CL01_ST_FAN', 'CL-01', 'CHILLER A1 FAN SPEED'),
    ('CL02_TT_OUT', 'CL-02', 'CHILLER B1 OUT TEMP'),
    ('CL02_ST_FAN', 'CL-02', 'CHILLER B1 FAN SPEED');

insert into readings (tag, measured_at, value) values
    ('CL01_TT_OUT', '2026-10-12 10:00:00+09', 58.4),
    ('CL01_TT_OUT', '2026-10-12 10:05:00+09', 61.0),
    ('CL01_TT_OUT', '2026-10-12 10:10:00+09', 63.2),
    ('CL01_FT',     '2026-10-12 10:10:00+09', 11.5),
    ('CL01_ST_FAN', '2026-10-12 10:10:00+09', 1180),
    ('CL02_TT_OUT', '2026-10-12 10:05:00+09', 40.6),
    ('CL02_TT_OUT', '2026-10-12 10:10:00+09', 41.0);
-- CL02_ST_FAN 은 센서 등록만 되어 있고 들어온 값이 없다.
