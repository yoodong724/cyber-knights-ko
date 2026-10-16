// Windows PowerShell 5.1 / .NET Framework. No download or administrator request.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Web.Script.Serialization;
using Microsoft.Win32.SafeHandles;

public static class CkfPatch {
    const long Limit = 536870912;
    static readonly string[] BasePaths = {
        "CyberKnights_Data/StreamingAssets/Locales/zh-CN.json",
        "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/735c930b6d62a5600e84bfa8a8b9dbb6.bundle",
        "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/137c9c9d0e2661b191cb5b5abcb264d0.bundle",
        "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/56da66cbd81e37886e44ed6c467fca8e.bundle",
    };
    static readonly string[] LegacyImagePaths = {
        "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/672fb9a7811edcdde218dc5de379c935.bundle",
        "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/b50ba8b5464ec4de8ea55b111bbad63a.bundle"
    };
    static readonly string[] CurrentImagePaths = {
        "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/427efad263b7a135a46a33ce3a2f2adf.bundle",
        "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/b50ba8b5464ec4de8ea55b111bbad63a.bundle"
    };
    static readonly string[] Guards = {
        "CyberKnights_Data/StreamingAssets/Locales/en-US.json",
        "CyberKnights_Data/StreamingAssets/aa/catalog.bin"
    };
    [StructLayout(LayoutKind.Sequential)] struct FileInfo {
        public uint Attributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME Creation, Access, Write;
        public uint Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool GetFileInformationByHandle(SafeFileHandle file, out FileInfo info);
    sealed class Row {
        public string Path, Before, After, Payload, PayloadHash;
        public long BeforeSize, AfterSize, PayloadSize;
    }
    sealed class Manifest {
        public string Id;
        public string PartialImageNotice;
        public Row[] Files;
        public Dictionary<string,string> Guards;
    }
    sealed class Conflict : IOException { public Conflict(string message) : base(message) {} }
    sealed class GuardLock : IDisposable {
        readonly List<FileStream> streams=new List<FileStream>();
        public GuardLock(string game,Manifest m) {
            try {
                foreach(string path in Guards) streams.Add(new FileStream(At(game,path),FileMode.Open,FileAccess.Read,FileShare.Read));
                CheckGuards(game,m);
            } catch { Dispose(); throw; }
        }
        public void Dispose() { foreach(var s in streams) s.Dispose(); }
    }
    static void Require(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
    static string Text(Dictionary<string,object> o, string key) {
        object v; Require(o.TryGetValue(key,out v) && v is string,"Invalid manifest field: " + key);
        return (string)v;
    }
    static long Number(Dictionary<string,object> o, string key) {
        object v; Require(o.TryGetValue(key,out v) && (v is int || v is long),"Invalid number: " + key);
        long n=Convert.ToInt64(v); Require(n>=0 && n<=Limit,"Number outside limit: " + key); return n;
    }
    static string DigestField(Dictionary<string,object> o, string key) {
        string s=Text(o,key); Require(Regex.IsMatch(s,"\\A[0-9a-f]{64}\\z"),"Invalid hash"); return s;
    }
    static Manifest ReadManifest(string path) {
        Safe(path); Require(new System.IO.FileInfo(path).Length < 1048576,"Manifest too large");
        var json=new JavaScriptSerializer();
        var root=json.DeserializeObject(File.ReadAllText(path,Encoding.UTF8)) as Dictionary<string,object>;
        Require(root!=null,"Invalid manifest");
        string format=Text(root,"format");
        Require(format=="ckf-distribution-v1" || format=="ckf-distribution-v2","Unsupported manifest");
        string build=Text(root,"steam_build"); long revision=Number(root,"revision");
        Require(Regex.IsMatch(build,"\\A[1-9][0-9]{0,19}\\z") && revision<=9999,"Invalid version");
        string id=build+(revision==0 ? "" : "-rc"+revision);
        Require(Text(root,"patch_id")==id,"Inconsistent version");
        string[] paths;
        if(format=="ckf-distribution-v1") {
            paths=(string[])BasePaths.Clone();
            if(build=="25889011") paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/f3165aa803db5d6316c3952a1d313627.bundle";
            if(build=="25951469" || build=="25964281") paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/12a93a93a631419a4acec10bebefc84a.bundle";
        }
        else {
            Require(build=="25594089" || build=="25697586" || build=="25889011" || build=="25951469" || build=="25964281","Unsupported image distribution build");
            string[] images=build=="25594089" ? LegacyImagePaths : CurrentImagePaths;
            paths=new string[6]; Array.Copy(BasePaths,paths,4); Array.Copy(images,0,paths,4,2);
            if(build=="25889011") paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/f3165aa803db5d6316c3952a1d313627.bundle";
            if(build=="25951469" || build=="25964281") paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/12a93a93a631419a4acec10bebefc84a.bundle";
        }
        var entries=root["files"] as object[]; Require(entries!=null && entries.Length==paths.Length,"Wrong file count");
        var result=new Manifest { Id=id,Files=new Row[paths.Length],Guards=new Dictionary<string,string>() };
        object imageStatus;
        if(root.TryGetValue("image_status",out imageStatus)) {
            var status=imageStatus as Dictionary<string,object>;
            Require(format=="ckf-distribution-v2" && (build=="25697586" || build=="25889011" || build=="25951469" || build=="25964281") && status!=null,"Invalid partial image profile");
            Require(Text(status,"source_build")==build,"Partial image source build mismatch");
            Require(Text(status,"format")=="ckf-partial-image-summary-v1","Unsupported image status");
            foreach(string key in new [] {"complete","human_language_approval","full_game_qa"}) {
                object value; Require(status.TryGetValue(key,out value) && value is bool && !(bool)value,"Invalid partial approval: "+key);
            }
            var edited=status["edited_ids"] as object[];
            Require(edited!=null && edited.Length>0 && edited.Length<=32,"Invalid partial image count");
            if(build=="25889011" || build=="25951469" || build=="25964281") {
                Require(Text(status,"evidence_source_build")=="25697586","Invalid reused image evidence build");
                var observed=status["ingame_observed_ids"] as object[];
                var notRun=status["ingame_not_run_ids"] as object[];
                Require(observed!=null && observed.Length==0 && notRun!=null && notRun.Length==edited.Length,"Old game QA cannot be reassigned");
            }
            long regions=Number(status,"rendered_regions"); Require(regions>0,"No partial image regions");
            result.PartialImageNotice="PARTIAL images: "+edited.Length+" images / "+regions+" regions. English text remains; full image/game QA is incomplete.";
        }
        for(int i=0;i<paths.Length;i++) {
            var r=entries[i] as Dictionary<string,object>; Require(r!=null,"Invalid file row");
            Require(Text(r,"path")==paths[i] && Text(r,"payload")=="payload/"+i+".delta.gz","Unexpected target or payload");
            result.Files[i]=new Row {Path=paths[i],Before=DigestField(r,"before"),After=DigestField(r,"after"),
                Payload=Text(r,"payload"),PayloadHash=DigestField(r,"payload_sha256"),
                BeforeSize=Number(r,"before_size"),AfterSize=Number(r,"after_size"),PayloadSize=Number(r,"payload_size")};
        }
        var guards=root["guards"] as object[]; Require(guards!=null && guards.Length==2,"Expected two guards");
        foreach(object item in guards) {
            var r=item as Dictionary<string,object>; Require(r!=null,"Invalid guard");
            string rel=Text(r,"path"); Require(Array.IndexOf(Guards,rel)>=0 && !result.Guards.ContainsKey(rel),"Unknown/duplicate guard");
            result.Guards.Add(rel,DigestField(r,"sha256"));
        }
        if(build=="25889011") {
            Require(result.Guards[Guards[0]]=="3888d0e89a488073871af9b40d74eb79e1d07330e552acb5a11bc5208bb74a3a" &&
                    result.Guards[Guards[1]]=="e38e0251c570115feea465d356c3db1011a09e80e7d162480f1a4ab29a79b59b","Guard/build profile mismatch");
        }
        if(build=="25951469") {
            Require(result.Guards[Guards[0]]=="02752bed120a3cd3bb1757b02c11bee6a8754b2a812f4ef890c0fa389bd3befb" &&
                    result.Guards[Guards[1]]=="382d80b33027e0bc863302c92c79fa84c39c717e3bb17daf991fa2409a545efe","Guard/build profile mismatch");
        }
        if(build=="25964281") {
            Require(result.Guards[Guards[0]]=="96b480317ed77cbd43ca6dcb87a8099a1eba29840512c02f69f33f89f8a30912" &&
                    result.Guards[Guards[1]]=="4730c1ddb4fe809e5835dda6b5251a114736ae05180fd98aef883fea1cab62bd","Guard/build profile mismatch");
        }
        if(format=="ckf-distribution-v2" && (build=="25889011" || build=="25951469" || build=="25964281")) Require(result.PartialImageNotice!=null,build+" images require partial status");
        if(format=="ckf-distribution-v2" && build!="25889011" && build!="25951469" && build!="25964281") {
            string english=build=="25594089" ? "6a0de0621ab04c4865cabcab5b3058ae854261f7952a0b3f0a44c1ec9c704c6a" : "dc181972ed1c734fdd703e7077af492972d9bdd9af212d8dbc8a2800c448e2d8";
            string catalog=build=="25594089" ? "08778902ee99fc8714d0c4752349075d002720a00162c9dad186c12d9f327133" : "48bb9cca0500656eede32b28a366e82f10a5cee54e3a02686a1e15234910954a";
            Require(result.Guards.Count==2 && result.Guards[Guards[0]]==english && result.Guards[Guards[1]]==catalog,"Guard/build profile mismatch");
        }
        return result;
    }
    static void Safe(string path) {
        string p=System.IO.Path.GetFullPath(path);
        while(!String.IsNullOrEmpty(p)) {
            try { Require((File.GetAttributes(p)&FileAttributes.ReparsePoint)==0,"Linked paths are not supported: "+p); }
            catch(FileNotFoundException) {} catch(DirectoryNotFoundException) {}
            string next=System.IO.Path.GetDirectoryName(p); if(next==p) break; p=next;
        }
        if(File.Exists(path)) {
            using(var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read)) {
                FileInfo info; Require(GetFileInformationByHandle(stream.SafeFileHandle,out info),"Cannot inspect file links");
                Require(info.Links==1,"Hardlinked files are not supported: "+path);
            }
        }
    }
    static string At(string root,string relative) {
        string p=System.IO.Path.GetFullPath(System.IO.Path.Combine(root,relative.Replace('/',System.IO.Path.DirectorySeparatorChar)));
        Require(p.StartsWith(root.TrimEnd('\\','/')+System.IO.Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase),"Path escapes root");
        Safe(p); return p;
    }
    static string Hash(string path) {
        Safe(path);
        using(var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.Read,1048576)) using(var sha=SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-","").ToLowerInvariant();
    }
    static void Check(string path,string expected) { Require(Hash(path)==expected,"Hash mismatch; no overwrite: "+path); }
    static void Idle() { Require(Process.GetProcessesByName("CyberKnights").Length==0,"Close CyberKnights before patching."); }
    static void CheckGuards(string game,Manifest m) { foreach(var pair in m.Guards) Check(At(game,pair.Key),pair.Value); }
    static void AtomicText(string path,string value) {
        Safe(path); string temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try { File.WriteAllText(temp,value,new UTF8Encoding(false));
            if(File.Exists(path)) File.Replace(temp,path,null); else File.Move(temp,path);
        } finally { if(File.Exists(temp)) File.Delete(temp); }
    }
    static void CopyNew(string source,string destination,string expected) {
        Safe(destination);
        if(File.Exists(destination)) { Check(destination,expected); return; }
        string temp=destination+"."+Guid.NewGuid().ToString("N")+".tmp";
        try { File.Copy(source,temp,false); Check(temp,expected); File.Move(temp,destination); }
        finally { if(File.Exists(temp)) File.Delete(temp); }
    }
    static byte[] Exact(BinaryReader r,int count) {
        byte[] bytes=r.ReadBytes(count); Require(bytes.Length==count,"Truncated delta"); return bytes;
    }
    static void Decode(string original,string delta,string output,long size) {
        Require(size>=0 && size<=Limit,"Output too large");
        Require(new System.IO.FileInfo(original).Length<=Limit,"Original too large");
        // COPY offsets are nonsequential. Buffer once rather than issuing thousands
        // of tiny disk/network seeks (especially on a WSL/UNC-backed game folder).
        using(var source=new MemoryStream(File.ReadAllBytes(original),false))
        using(var input=new FileStream(delta,FileMode.Open,FileAccess.Read,FileShare.Read,1048576))
        using(var zip=new GZipStream(input,CompressionMode.Decompress)) using(var r=new BinaryReader(zip))
        using(var target=new FileStream(output,FileMode.CreateNew,FileAccess.Write,FileShare.None,65536)) {
            Require(Encoding.ASCII.GetString(Exact(r,8))=="CKFDLT1\0" && r.ReadUInt64()==(ulong)size,"Invalid delta header");
            byte[] buffer=new byte[65536]; long written=0;
            while(true) {
                int op=r.ReadByte(); if(op==0) { Require(written==size && zip.ReadByte()==-1,"Invalid delta end"); break; }
                Require(op==1 || op==2,"Unknown delta opcode");
                ulong offset=op==1 ? r.ReadUInt64() : 0; uint length=r.ReadUInt32();
                Require(length>0 && length<=size-written,"Delta overflow");
                if(op==1) {
                    Require(offset<=(ulong)source.Length && length<=(ulong)source.Length-offset,"Copy outside source");
                    source.Position=(long)offset;
                }
                long left=length;
                while(left>0) {
                    int count=(int)Math.Min(left,buffer.Length);
                    int got=op==1 ? source.Read(buffer,0,count) : zip.Read(buffer,0,count);
                    Require(got>0,"Truncated delta data"); target.Write(buffer,0,got); left-=got;
                }
                written+=length;
            }
            target.Flush(true);
        }
    }
    static void BackupChecks(string backup,Manifest m,string manifestHash) {
        Check(At(backup,"manifest.json"),manifestHash);
        for(int i=0;i<m.Files.Length;i++) Check(At(backup,i+".original"),m.Files[i].Before);
    }
    static void KnownTargets(string game,Manifest m) {
        foreach(Row r in m.Files) {
            string hash=Hash(At(game,r.Path)); Require(hash==r.Before || hash==r.After,"External change detected; keep files and backup: "+r.Path);
        }
    }
    static void ReplaceChecked(string source,string target,string backup,string before,string after) {
        Idle(); Check(target,before);
        string displaced=At(backup,"displaced-"+Guid.NewGuid().ToString("N")+".bin");
        File.Replace(source,target,displaced);
        if(Hash(displaced)!=before || Hash(target)!=after) {
            AtomicText(At(backup,"state.txt"),"CONFLICT");
            throw new Conflict("Concurrent file change. No automatic overwrite. Preserved file: "+displaced);
        }
        File.Delete(displaced);
    }
    static void CleanWork(string backup,Manifest m) {
        // Validate every work directory before deleting anything. Keep all displaced evidence.
        var dirs=Directory.GetDirectories(backup,"work-*");
        foreach(string dir in dirs) {
            Safe(dir);
            Require(Regex.IsMatch(System.IO.Path.GetFileName(dir),"\\Awork-[0-9a-f]{32}\\z"),"Unknown work directory");
            Require(Directory.GetDirectories(dir).Length==0,"Nested work directory");
            foreach(string p in Directory.GetFiles(dir)) {
                Safe(p); string name=System.IO.Path.GetFileName(p);
                bool allowed=false;
                for(int i=0;i<m.Files.Length;i++) if(name==i+".patched") allowed=true;
                Require(allowed,"Unknown file in work directory");
            }
        }
        foreach(string dir in dirs) {
            foreach(string p in Directory.GetFiles(dir)) File.Delete(p);
            Directory.Delete(dir,false);
        }
    }
    static void Restore(string game,string backup,Manifest m,string manifestHash) {
        CheckGuards(game,m); BackupChecks(backup,m,manifestHash); KnownTargets(game,m); Idle();
        Require(!File.Exists(At(backup,"state.txt")) || File.ReadAllText(At(backup,"state.txt"))!="CONFLICT","Concurrent-change evidence requires manual recovery; backup retained");
        AtomicText(At(backup,"state.txt"),"RESTORING");
        for(int i=0;i<m.Files.Length;i++) {
            Row r=m.Files[i]; string target=At(game,r.Path);
            if(Hash(target)==r.Before) continue;
            string temp=At(backup,"restore-"+Guid.NewGuid().ToString("N")+".tmp");
            try { File.Copy(At(backup,i+".original"),temp,false); Check(temp,r.Before);
                ReplaceChecked(temp,target,backup,r.After,r.Before);
            } finally { if(File.Exists(temp)) File.Delete(temp); }
        }
        foreach(Row r in m.Files) Check(At(game,r.Path),r.Before);
        AtomicText(At(backup,"state.txt"),"RESTORED");
        CleanWork(backup,m);
    }
    public static int Run(string package,string mode,bool unattended) {
        try {
            Require(mode=="install" || mode=="uninstall" || mode=="verify","Invalid mode");
            package=System.IO.Path.GetFullPath(package).TrimEnd('\\','/'); Safe(package);
            Require(System.IO.Path.GetFileName(package)=="cyberknights-ko","Extract as GAME\\cyberknights-ko\\install.cmd");
            string game=Directory.GetParent(package).FullName; Safe(game);
            Require(!game.StartsWith("\\\\",StringComparison.Ordinal) &&
                new DriveInfo(System.IO.Path.GetPathRoot(game)).DriveFormat=="NTFS",
                "Extract into the game's local NTFS drive. Network/WSL UNC folders are not supported.");
            Require(File.Exists(At(game,"CyberKnights.exe")) && Directory.Exists(At(game,"CyberKnights_Data")),"Parent is not the CyberKnights game folder.");
            string manifestPath=At(package,"manifest.json"); Manifest m=ReadManifest(manifestPath); string manifestHash=Hash(manifestPath);
            Idle(); CheckGuards(game,m);
            foreach(Row r in m.Files) {
                Require(File.Exists(At(game,r.Path)),"Missing game file: "+r.Path);
                if(mode!="uninstall") {
                    string p=At(package,r.Payload); Require(new System.IO.FileInfo(p).Length==r.PayloadSize,"Payload size mismatch"); Check(p,r.PayloadHash);
                }
            }
            KnownTargets(game,m);
            if(m.PartialImageNotice!=null) Console.WriteLine(m.PartialImageNotice);
            if(mode=="verify") {
                foreach(Row r in m.Files) Check(At(game,r.Path),r.After);
                Console.WriteLine("Verified Korean patch: "+m.Id); return 0;
            }
            Console.WriteLine("Target: "+game); Console.WriteLine("Patch: "+m.Id+" / "+mode);
            if(!unattended) { Console.Write("Continue? [y/N] "); if(!String.Equals(Console.ReadLine(),"y",StringComparison.OrdinalIgnoreCase)) return 2; }
            string lockPath=At(game,".cyberknights-ko.lock");
            using(var held=new FileStream(lockPath,FileMode.OpenOrCreate,FileAccess.ReadWrite,FileShare.None))
            using(var guards=new GuardLock(game,m)) {
                Idle(); CheckGuards(game,m); KnownTargets(game,m);
                string backup=At(game,".cyberknights-ko-backup/"+m.Id);
                Console.WriteLine("Backup: "+backup);
                if(mode=="uninstall") { Restore(game,backup,m,manifestHash); Console.WriteLine("Original files restored. Backup retained."); return 0; }
                string state=At(backup,"state.txt");
                bool ready=File.Exists(state);
                if(ready) {
                    Require(new[]{"PREPARED","APPLIED","RESTORED","RESTORING"}.ContainsValue(File.ReadAllText(state)),"Unknown/conflict backup state; preserve backup and request recovery");
                    BackupChecks(backup,m,manifestHash);
                } else {
                    foreach(Row r in m.Files) Check(At(game,r.Path),r.Before);
                    Directory.CreateDirectory(backup); Safe(backup);
                    CopyNew(manifestPath,At(backup,"manifest.json"),manifestHash);
                    for(int i=0;i<m.Files.Length;i++) CopyNew(At(game,m.Files[i].Path),At(backup,i+".original"),m.Files[i].Before);
                    BackupChecks(backup,m,manifestHash); AtomicText(state,"PREPARED");
                }
                CleanWork(backup,m);
                bool already=true; foreach(Row r in m.Files) if(Hash(At(game,r.Path))!=r.After) already=false;
                if(already) { AtomicText(state,"APPLIED"); Console.WriteLine("Already installed; verified."); return 0; }
                string work=At(backup,"work-"+Guid.NewGuid().ToString("N")); Directory.CreateDirectory(work);
                // Materialize and hash every output before the first game file changes.
                for(int i=0;i<m.Files.Length;i++) {
                    Row r=m.Files[i]; string payload=At(package,r.Payload); Check(payload,r.PayloadHash);
                    Decode(At(backup,i+".original"),payload,At(work,i+".patched"),r.AfterSize); Check(At(work,i+".patched"),r.After);
                }
                BackupChecks(backup,m,manifestHash); CheckGuards(game,m); KnownTargets(game,m); Idle();
                AtomicText(state,"PREPARED");
                try {
                    for(int i=0;i<m.Files.Length;i++) {
                        Row r=m.Files[i]; string target=At(game,r.Path); string current=Hash(target);
                        Require(current==r.Before || current==r.After,"Concurrent change detected");
                        if(current!=r.After) ReplaceChecked(At(work,i+".patched"),target,backup,r.Before,r.After);
                    }
                    foreach(Row r in m.Files) Check(At(game,r.Path),r.After);
                    AtomicText(state,"APPLIED");
                } catch(Conflict) { throw;
                } catch {
                    Console.WriteLine("Install interrupted. Attempting guarded restore.");
                    Restore(game,backup,m,manifestHash); throw;
                }
                CleanWork(backup,m);
                Console.WriteLine("Korean patch installed. Select Korean in the game language menu.");
                Console.WriteLine("Existing saved character names are not renamed."); return 0;
            }
        } catch(Exception e) { Console.Error.WriteLine("Patch stopped: "+e.Message); return 1; }
    }
    static bool ContainsValue(this string[] values,string value) { return Array.IndexOf(values,value)>=0; }
}
