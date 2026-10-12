using System;
using System.IO;
using System.IO.Compression;
using System.Text;

// BC1/BC2/BC3 DDS and documented DST1/DST5 shuffle -> lossless RGBA PNG.
public static class SimsTextureReader
{
    static uint U(byte[] b,int p)=>BitConverter.ToUInt32(b,p);
    public static byte[] Png(byte[] bytes)
    {
        if(bytes.Length>=8&&bytes[0]==137&&Encoding.ASCII.GetString(bytes,1,3)=="PNG")return bytes;
        if(bytes.Length<128||U(bytes,0)!=0x20534444||U(bytes,4)!=124||U(bytes,76)!=32)throw new NotSupportedException("Texture is not supported PNG/DDS");
        int height=checked((int)U(bytes,12)),width=checked((int)U(bytes,16));
        if(width<1||height<1||width>4096||height>4096)throw new NotSupportedException("Texture dimensions exceed 4096 limit");
        if((U(bytes,112)&0xFE00)!=0||U(bytes,24)>1)throw new NotSupportedException("Cube/volume textures are unsupported");
        string format=Encoding.ASCII.GetString(bytes,84,4);int blockSize=format=="DXT1"||format=="DST1"?8:format=="DXT3"||format=="DXT5"||format=="DST5"?16:0;
        if(blockSize==0)throw new NotSupportedException("Unsupported DDS format "+format);
        int payload=bytes.Length-128;if(payload%blockSize!=0)throw new FormatException("Invalid DDS block payload");
        var data=new byte[payload];Buffer.BlockCopy(bytes,128,data,0,payload);
        if(format=="DST1"||format=="DST5") {
            int blocks=payload/blockSize;var unshuffled=new byte[payload];
            for(int i=0;i<blocks;i++) {
                int at=i*blockSize;
                if(blockSize==8){Buffer.BlockCopy(data,i*4,unshuffled,at,4);Buffer.BlockCopy(data,blocks*4+i*4,unshuffled,at+4,4);}
                else {Buffer.BlockCopy(data,i*2,unshuffled,at,2);Buffer.BlockCopy(data,blocks*6+i*6,unshuffled,at+2,6);Buffer.BlockCopy(data,blocks*2+i*4,unshuffled,at+8,4);Buffer.BlockCopy(data,blocks*12+i*4,unshuffled,at+12,4);}
            }data=unshuffled;
        }
        int columns=(width+3)/4,rows=(height+3)/4;if((long)columns*rows*blockSize>data.Length)throw new FormatException("Truncated DDS mip");
        var pixels=new byte[checked(width*height*4)];
        for(int y=0;y<rows;y++)for(int x=0;x<columns;x++) {
            int at=(y*columns+x)*blockSize,colors=at+(blockSize==16?8:0);ushort c0=BitConverter.ToUInt16(data,colors),c1=BitConverter.ToUInt16(data,colors+2);
            var palette=new byte[4,4];Color(palette,0,c0);Color(palette,1,c1);
            for(int c=0;c<3;c++) {
                palette[2,c]=(byte)(c0>c1||blockSize==16?(2*palette[0,c]+palette[1,c])/3:(palette[0,c]+palette[1,c])/2);
                palette[3,c]=(byte)(c0>c1||blockSize==16?(palette[0,c]+2*palette[1,c])/3:0);
            }palette[2,3]=255;palette[3,3]=(byte)(c0>c1||blockSize==16?255:0);
            uint indices=U(data,colors+4);var alpha=new byte[8];ulong alphaIndices=0;
            if(blockSize==16&&format!="DXT3") {
                alpha[0]=data[at];alpha[1]=data[at+1];
                if(alpha[0]>alpha[1])for(int i=2;i<8;i++)alpha[i]=(byte)(((8-i)*alpha[0]+(i-1)*alpha[1])/7);
                else {for(int i=2;i<6;i++)alpha[i]=(byte)(((6-i)*alpha[0]+(i-1)*alpha[1])/5);alpha[6]=0;alpha[7]=255;}
                for(int i=0;i<6;i++)alphaIndices|=(ulong)data[at+2+i]<<(8*i);
            }
            for(int j=0;j<16;j++) {
                int px=x*4+j%4,py=y*4+j/4;if(px>=width||py>=height)continue;int dst=(py*width+px)*4,index=(int)((indices>>(2*j))&3);
                for(int c=0;c<4;c++)pixels[dst+c]=palette[index,c];
                if(blockSize==16)pixels[dst+3]=format=="DXT3"?(byte)(((data[at+j/2]>>((j%2)*4))&15)*17):alpha[(int)((alphaIndices>>(3*j))&7)];
            }
        }return Encode(width,height,pixels);
    }
    static void Color(byte[,] p,int i,ushort color){int r=(color>>11)&31,g=(color>>5)&63,b=color&31;p[i,0]=(byte)((r<<3)|(r>>2));p[i,1]=(byte)((g<<2)|(g>>4));p[i,2]=(byte)((b<<3)|(b>>2));p[i,3]=255;}
    static void Big(Stream s,uint value){for(int i=3;i>=0;i--)s.WriteByte((byte)(value>>(i*8)));}
    static void Chunk(Stream output,string name,byte[] data){Big(output,(uint)data.Length);byte[] tag=Encoding.ASCII.GetBytes(name);output.Write(tag,0,4);output.Write(data,0,data.Length);uint crc=0xffffffff;foreach(byte b in tag)crc=Step(crc,b);foreach(byte b in data)crc=Step(crc,b);Big(output,crc^0xffffffff);}
    static uint Step(uint crc,byte b){crc^=b;for(int i=0;i<8;i++)crc=(crc>>1)^((crc&1)!=0?0xedb88320u:0);return crc;}
    static byte[] Encode(int width,int height,byte[] pixels)
    {
        using(var output=new MemoryStream()) {
            output.Write(new byte[]{137,80,78,71,13,10,26,10},0,8);
            using(var header=new MemoryStream()){Big(header,(uint)width);Big(header,(uint)height);header.Write(new byte[]{8,6,0,0,0},0,5);Chunk(output,"IHDR",header.ToArray());}
            var raw=new byte[checked((width*4+1)*height)];for(int y=0;y<height;y++)Buffer.BlockCopy(pixels,y*width*4,raw,y*(width*4+1)+1,width*4);
            using(var zlib=new MemoryStream()) {
                zlib.WriteByte(0x78);zlib.WriteByte(0x9c);using(var deflate=new DeflateStream(zlib,CompressionLevel.Optimal,true))deflate.Write(raw,0,raw.Length);
                uint a=1,b=0;foreach(byte value in raw){a=(a+value)%65521;b=(b+a)%65521;}Big(zlib,(b<<16)|a);Chunk(output,"IDAT",zlib.ToArray());
            }Chunk(output,"IEND",new byte[0]);return output.ToArray();
        }
    }
}
