import sys, zlib, struct
def load(path):
    data=open(path,'rb').read()
    assert data[:8]==b'\x89PNG\r\n\x1a\n'
    pos=8; idat=b''; w=h=None
    while pos<len(data):
        ln=struct.unpack('>I',data[pos:pos+4])[0]; typ=data[pos+4:pos+8]; body=data[pos+8:pos+8+ln]; pos+=12+ln
        if typ==b'IHDR':
            w,h,bd,ct,cm,fm,il=struct.unpack('>IIBBBBB',body)
        elif typ==b'IDAT': idat+=body
        elif typ==b'IEND': break
    raw=zlib.decompress(idat)
    bpp={2:3,6:4,0:1,4:2}[ct]
    stride=w*bpp; rows=[]; prev=bytearray(stride); i=0
    for y in range(h):
        f=raw[i]; i+=1; line=bytearray(raw[i:i+stride]); i+=stride
        for x in range(stride):
            a=line[x-bpp] if x>=bpp else 0; b=prev[x]; c=prev[x-bpp] if x>=bpp else 0
            if f==1: line[x]=(line[x]+a)&255
            elif f==2: line[x]=(line[x]+b)&255
            elif f==3: line[x]=(line[x]+((a+b)>>1))&255
            elif f==4:
                p=a+b-c; pa=abs(p-a); pb=abs(p-b); pc=abs(p-c)
                pr=a if pa<=pb and pa<=pc else (b if pb<=pc else c)
                line[x]=(line[x]+pr)&255
        rows.append(bytes(line)); prev=line
    return w,h,bpp,rows
def px(img,x,y):
    w,h,bpp,rows=img; r=rows[y]; return tuple(r[x*bpp:x*bpp+3])
if __name__=='__main__':
    img=load(sys.argv[1])
    for spec in sys.argv[2:]:
        name,x0,y0,x1,y1=spec.split(',')
        x0,y0,x1,y1=map(int,(x0,y0,x1,y1))
        cols={}
        for y in range(y0,y1):
            for x in range(x0,x1):
                c=px(img,x,y)
                if sum(c)<600: cols[c]=cols.get(c,0)+1
        top=sorted(cols.items(),key=lambda kv:-kv[1])[:3]
        print(name, top)
