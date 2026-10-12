using System;
class Program
{
    static bool cancel;
    static int Main(string[] args)
    {
        if(args.Length!=2){Console.Error.WriteLine("Usage: SimsExport <game/package-folder> <separate-output-folder>");return 2;}
        Console.CancelKeyPress+=(sender,e)=>{e.Cancel=true;cancel=true;};
        try{string source=System.IO.File.Exists(args[0])?SimsBatchExporter.InstallationFromExe(args[0]):args[0];return SimsBatchExporter.Run(source,args[1],Console.WriteLine,()=>cancel);}
        catch(Exception error){Console.Error.WriteLine(error.Message);return 2;}
    }
}
