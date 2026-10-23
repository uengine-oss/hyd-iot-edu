import sys, json
src, dst, chg = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(src, encoding='utf-8').read()
cut = text.index('## [SLIDE 29]')
head, tail = text[:cut], text[cut:]
changes = json.load(open(chg, encoding='utf-8'))
for c in changes:
    old, new = c['old'], c['new']
    n_all = text.count(old)
    n_head = head.count(old)
    assert n_all == 1 and n_head == 1, (c['id'], n_all, n_head)
    head = head.replace(old, new, 1)
out = head + tail
open(dst, 'w', encoding='utf-8').write(out)
print('ok', len(changes))
