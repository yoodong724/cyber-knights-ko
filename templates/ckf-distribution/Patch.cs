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
    static readonly string[] Originals26097464 = {
        "46b39cf4d342bb6901ee7d07e03e6425dcebc92c98e8bd8c76d3473f98218c45",
        "876d7d2963fa00e6752e961d845fe59fb41f3a9c204226c35a74a122e85bc770",
        "9b4db040dcf96a3d123ca23f0716423c7f25aed2596f5952cf8102d53b6464f7",
        "7398233a5ef51249b296057a634b3bc3d5726f102d7435c2199efb566998bbe6",
        "506252c273a6a770a8547d1c299386760fe8f0c05c2f7ba2277e8da2854ae792",
        "b09d2e824819be5a672cc5211b69e2c4e339181426a2c40dcbe2a283e984209f",
    };
    static readonly string[] Originals26138768 = {
        "25d244ba3aa65f5ba4401dbe86095c4dd5b5f8f2469e3e03cc5f0e8d97699921",
        "876d7d2963fa00e6752e961d845fe59fb41f3a9c204226c35a74a122e85bc770",
        "9b4db040dcf96a3d123ca23f0716423c7f25aed2596f5952cf8102d53b6464f7",
        "7398233a5ef51249b296057a634b3bc3d5726f102d7435c2199efb566998bbe6",
        "6fbec86410d658743b498efc3ed071d480b8f96f1603fa61cdd8e577e68dbac4",
        "b09d2e824819be5a672cc5211b69e2c4e339181426a2c40dcbe2a283e984209f",
    };
    static readonly string[] Originals26198171 = {
        "25d244ba3aa65f5ba4401dbe86095c4dd5b5f8f2469e3e03cc5f0e8d97699921",
        "876d7d2963fa00e6752e961d845fe59fb41f3a9c204226c35a74a122e85bc770",
        "7870560393372f4162d75e52b387f0dfc655b4cf91a71b08e6202880e0496bd0",
        "ab461ecfd3641ff9e6f3c65cb328a25f4398699a36f9fc988033acbdddb9cce1",
        "5c0d00b591057234a86e8e1cc4a527dd6591d59baf9215ca585303f38b98e351",
        "7177b7ccde4e3a809c88c6cdd901d47b334a0001cd0af801c7c6155d2625f876",
    };
    // Builds whose reviewed image streams are relocated from the 25964281-rc1 evidence.
    static bool Relocated(string build) { return build=="26097464" || build=="26138768" || build=="26151125" || build=="26198171"; }
    static readonly string[] RelocationIds = {
        "ckf-image:229f9cc082b71e3e35ac8493bc326831a23275e35f8250d1eab95d625da52204",
        "ckf-image:35f5cc5cc055b936df5ba6cf9ece3da2216d315325b57081b52e24b6e72d8805",
        "ckf-image:43991411c1b1c9cb9f5eae019dd770f1e38fa21956c9feed2d8e2356a76dcb1a",
        "ckf-image:462779d03956d564c85cdd5ae1d56cc7705e3dfc32b28bc2f00ca328f7c87419",
        "ckf-image:5839833ff1ea3612c87a05fe4c0395d3cfcb36a8c0565efb6fef705763fcd07d",
        "ckf-image:6c46f4faa8be3818380e8e899c0003a392126dfa830145347f0baf15b05760f8",
        "ckf-image:81217ca4baf4fb79b81a1a4a232b6d3a56fb7a945149d2fe6fd5ae8bf0d4416c",
        "ckf-image:8f86df2a12380c113d23a6a87f32b98e08c8354ebf0c7c26a507d44390fad5cd",
        "ckf-image:959312b069b2623dfad1a642f3f130aac7b578357eefcc7d8dd151a0f9dec709",
        "ckf-image:962554279f206d7f3b54433efbbff3334408cd1ee5073cc6f183786eecf8c631",
        "ckf-image:c08ef01819bdac7c2aab9987fe6ccd72c066da7d0edbb5b1ff99a4cf9104ce5d",
        "ckf-image:cdd3e1ed2e58a935c83dc0d06c7e6c13de1a2a2fed97b0a9e7232fe7e42fd353",
        "ckf-image:d32acc60a653bf9c704dcd7a7ac4747f0e3c06844837f3fdff6dc2a1c4746fe2",
        "ckf-image:d4a5d3d283108352084f19c27bbf52b35738bc012f2312f342fac689ce0f7ea7",
        "ckf-image:da5c48a987c641e264fb2fdf43f53223dd11a49ce3a31fc2eb72b602135920ad",
        "ckf-image:e2e6c28b3728ed018900074010c260f450b4951b7d80d73a62c42f4c725c7ab5",
    };
    static readonly string[] RelocationScopeIds = {
        "ckf-image:10fa5342868340bff4037730a670069c2e6e4eef7bf090150f2780354c248e71",
        "ckf-image:229f9cc082b71e3e35ac8493bc326831a23275e35f8250d1eab95d625da52204",
        "ckf-image:34a9bbe24b1b4befdd3cf4a26824fb71a17d5cfa3455d53a7ae28ece0dd5a08f",
        "ckf-image:35f5cc5cc055b936df5ba6cf9ece3da2216d315325b57081b52e24b6e72d8805",
        "ckf-image:39f90ba38f882d2e11c171055e5a61d20cc9b5ffcf525ac450793bd43c2d7b26",
        "ckf-image:43991411c1b1c9cb9f5eae019dd770f1e38fa21956c9feed2d8e2356a76dcb1a",
        "ckf-image:462779d03956d564c85cdd5ae1d56cc7705e3dfc32b28bc2f00ca328f7c87419",
        "ckf-image:4cd44412ec186759eb6f8b53f5f7e82d2b075e863440694f085a4f9b888e84e8",
        "ckf-image:5839833ff1ea3612c87a05fe4c0395d3cfcb36a8c0565efb6fef705763fcd07d",
        "ckf-image:66a6e0d543860a4e38e193737acbf195c6f9c40864a667ff0f8166443364e0d6",
        "ckf-image:6a97d5c1701bdaff024f3ebb86bcacaa4f5c7a3c61b3255fea0407b3587c88e7",
        "ckf-image:6c46f4faa8be3818380e8e899c0003a392126dfa830145347f0baf15b05760f8",
        "ckf-image:81217ca4baf4fb79b81a1a4a232b6d3a56fb7a945149d2fe6fd5ae8bf0d4416c",
        "ckf-image:8d14daa5de7063d4c59364a3e419bd7154657e0aaa042ad0b0610e87343b514a",
        "ckf-image:8f86df2a12380c113d23a6a87f32b98e08c8354ebf0c7c26a507d44390fad5cd",
        "ckf-image:959312b069b2623dfad1a642f3f130aac7b578357eefcc7d8dd151a0f9dec709",
        "ckf-image:962554279f206d7f3b54433efbbff3334408cd1ee5073cc6f183786eecf8c631",
        "ckf-image:9a9baef7b49fd2ee66f8f76fdad6bc545e1e4faac86f997ffb34259cd6027200",
        "ckf-image:9ba86746f425e1c9fd0dcfcd68f737a6991d0c45f83c76a0f933b649971d9007",
        "ckf-image:c08ef01819bdac7c2aab9987fe6ccd72c066da7d0edbb5b1ff99a4cf9104ce5d",
        "ckf-image:c1dfb8444300f56f8878a922f6f7cc1b26b823a3cb1a3ec900d595fdfcb0de4e",
        "ckf-image:c9773b7be4d773f10eff76701a65872660a3b0cff7a059638f7e27e9226401e9",
        "ckf-image:cd1971a4c5e7966a9c190a1b3401f39b927f187f0b2325875ec8bbe5ec6ee1e3",
        "ckf-image:cdd3e1ed2e58a935c83dc0d06c7e6c13de1a2a2fed97b0a9e7232fe7e42fd353",
        "ckf-image:d0b4328542a83b41f8e3af60af6fc4abd0b91eb63214bc2258e799afa6681c69",
        "ckf-image:d32acc60a653bf9c704dcd7a7ac4747f0e3c06844837f3fdff6dc2a1c4746fe2",
        "ckf-image:d4a5d3d283108352084f19c27bbf52b35738bc012f2312f342fac689ce0f7ea7",
        "ckf-image:d8dce10299f163f564e360a4ff8445b0935cee1804aad2be20dd38e4bd5510ec",
        "ckf-image:da5c48a987c641e264fb2fdf43f53223dd11a49ce3a31fc2eb72b602135920ad",
        "ckf-image:e2e6c28b3728ed018900074010c260f450b4951b7d80d73a62c42f4c725c7ab5",
        "ckf-image:f07c6b2b1446d03d4d2dc543584f7ff1bac92727dcff305f4fa490d9a8276632",
        "ckf-image:f54efe3c47127023886e8b7b0177d5a4ac064a739577e7bfc7dca692665cb6fc",
        "ckf-image:f9cb0933f1e81af8cc9b0d9ba4a308f110c7af7ca98285c60ee119b3077360b6",
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
    static HashSet<string> ImageIds(Dictionary<string,object> status,string key,int count) {
        object value; Require(status.TryGetValue(key,out value),"Missing image IDs: "+key);
        var values=value as object[]; Require(values!=null && values.Length==count,"Wrong image count: "+key);
        var found=new HashSet<string>(StringComparer.Ordinal);
        foreach(object item in values) Require(item is string && Regex.IsMatch((string)item,"\\Ackf-image:[0-9a-f]{64}\\z") && found.Add((string)item),"Invalid/duplicate image ID: "+key);
        return found;
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
        if(build=="26097464") Require(format=="ckf-distribution-v2" && Text(root,"game_version")=="2.7.99","26097464 requires its six-file image profile");
        if(build=="26138768") Require(format=="ckf-distribution-v2" && Text(root,"game_version")=="2.7.101","26138768 requires its six-file image profile");
        if(build=="26151125") Require(format=="ckf-distribution-v2" && Text(root,"game_version")=="2.7.103","26151125 requires its six-file image profile");
        if(build=="26198171") Require(format=="ckf-distribution-v2" && Text(root,"game_version")=="2.7.105","26198171 requires its six-file image profile");
        string[] paths;
        if(format=="ckf-distribution-v1") {
            paths=(string[])BasePaths.Clone();
            if(build=="25889011") paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/f3165aa803db5d6316c3952a1d313627.bundle";
            if(build=="25951469" || build=="25964281") paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/12a93a93a631419a4acec10bebefc84a.bundle";
        }
        else {
            Require(build=="25594089" || build=="25697586" || build=="25889011" || build=="25951469" || build=="25964281" || Relocated(build),"Unsupported image distribution build");
            string[] images=build=="25594089" ? LegacyImagePaths : CurrentImagePaths;
            paths=new string[6]; Array.Copy(BasePaths,paths,4); Array.Copy(images,0,paths,4,2);
            if(build=="25889011") paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/f3165aa803db5d6316c3952a1d313627.bundle";
            if(build=="25951469" || build=="25964281") paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/12a93a93a631419a4acec10bebefc84a.bundle";
            if(Relocated(build)) {
                paths[1]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/f1335b489121d5d0f88f37fff58849d9.bundle";
                paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/81abd4ea29932d9b79d378d018b7d98a.bundle";
                paths[3]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/b19430f3a52557e1df858dc46e1b0233.bundle";
                paths[4]=build=="26097464" ? "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/53eac8afc5b57b0740ef08e062c1268b.bundle"
                                           : "CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/b495bc337d998091a40d0c5cebf7b587.bundle";
            }
        }
        if(build=="26198171") {
            paths[2]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/6f7da796053120e53bb28f13b9af03e7.bundle";
            paths[3]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/c8ff7ba58183d5beda8e7cdce8c2ebfa.bundle";
            paths[4]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/804228c7e0a40ff579ed96ad65e37333.bundle";
            paths[5]="CyberKnights_Data/StreamingAssets/aa/StandaloneWindows64/d31ee332273542d2e40d9d454e972012.bundle";
        }
        var entries=root["files"] as object[]; Require(entries!=null && entries.Length==paths.Length,"Wrong file count");
        var result=new Manifest { Id=id,Files=new Row[paths.Length],Guards=new Dictionary<string,string>() };
        object imageStatus;
        if(root.TryGetValue("image_status",out imageStatus)) {
            var status=imageStatus as Dictionary<string,object>;
            Require(format=="ckf-distribution-v2" && (build=="25697586" || build=="25889011" || build=="25951469" || build=="25964281" || Relocated(build)) && status!=null,"Invalid partial image profile");
            Require(Text(status,"source_build")==build,"Partial image source build mismatch");
            Require(Text(status,"format")=="ckf-partial-image-summary-v1","Unsupported image status");
            foreach(string key in new [] {"complete","human_language_approval","full_game_qa"}) {
                object value; Require(status.TryGetValue(key,out value) && value is bool && !(bool)value,"Invalid partial approval: "+key);
            }
            var edited=status["edited_ids"] as object[];
            Require(edited!=null && edited.Length>0 && edited.Length<=32,"Invalid partial image count");
            if(build=="25889011" || build=="25951469" || build=="25964281" || Relocated(build)) {
                Require(Text(status,"evidence_source_build")=="25697586","Invalid reused image evidence build");
                var observed=status["ingame_observed_ids"] as object[];
                var notRun=status["ingame_not_run_ids"] as object[];
                Require(observed!=null && observed.Length==0 && notRun!=null && notRun.Length==edited.Length,"Old game QA cannot be reassigned");
            }
            long regions=Number(status,"rendered_regions"); Require(regions>0,"No partial image regions");
            if(Relocated(build)) {
                Require(regions==67,"Relocation region count mismatch");
                object available;
                Require(status.TryGetValue("historical_ingame_evidence_available",out available) && available is bool && !(bool)available,"Historical game evidence is unavailable");
                var evidence=status["evidence_sha256"] as Dictionary<string,object>;
                Require(evidence!=null && DigestField(evidence,"prior_archive")=="4833ae1876c9572100815df8045948eba80717182f4b894ba332fcbaad96983f","Wrong released image evidence anchor");
                foreach(string key in new [] {"relocation_stage_manifest","relocation_receipt","current_machine_report"}) DigestField(evidence,key);
                var expected=new HashSet<string>(RelocationIds,StringComparer.Ordinal);
                foreach(string key in new [] {"edited_ids","ingame_not_run_ids"}) Require(ImageIds(status,key,16).SetEquals(expected),"Invalid relocation evidence IDs");
                Require(ImageIds(status,"partial_ids",11).IsSubsetOf(expected),"Invalid partially edited IDs");
                Require(ImageIds(status,"held_ids",2).SetEquals(new [] {"ckf-image:10fa5342868340bff4037730a670069c2e6e4eef7bf090150f2780354c248e71","ckf-image:66a6e0d543860a4e38e193737acbf195c6f9c40864a667ff0f8166443364e0d6"}),"Invalid held image IDs");
                Require(ImageIds(status,"retained_ids",1).Contains("ckf-image:6a97d5c1701bdaff024f3ebb86bcacaa4f5c7a3c61b3255fea0407b3587c88e7"),"Invalid retained image ID");
                var all=new HashSet<string>(expected,StringComparer.Ordinal);
                all.UnionWith(ImageIds(status,"held_ids",2));
                all.UnionWith(ImageIds(status,"unrendered_ids",14));
                all.UnionWith(ImageIds(status,"retained_ids",1));
                Require(all.SetEquals(RelocationScopeIds),"Invalid historical image partition");
            }
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
        if(build=="26097464") {
            Require(result.Guards[Guards[0]]=="f9f37a09c8f7ac1057612c5c1682d6df9cf958e8bd5c757e637764bd7b9e5077" &&
                    result.Guards[Guards[1]]=="e45b4dd2c6cb0e760f994a58c3fa98fe49eb0474b136eb0ba8a7ab8a7b0b4d55","Guard/build profile mismatch");
            for(int i=0;i<paths.Length;i++) Require(result.Files[i].Before==Originals26097464[i],"Original target/build profile mismatch");
            Require(result.Files[1].After=="d23a95d170c98458973281a24c15b06b5e1065bdab6eda0d533880f2ee0730cc","Unverified 26097464 font result");
        }
        if(build=="26138768") {
            Require(result.Guards[Guards[0]]=="00c771cb9534cdfca3ce51acd98e6b1cf8a4ee75dcef6ee34c49bd27ed52de3a" &&
                    result.Guards[Guards[1]]=="56778d83a2fd108ebab4311a6639b9705750fb967705ff9a6852ef1c977f9d13","Guard/build profile mismatch");
            for(int i=0;i<paths.Length;i++) Require(result.Files[i].Before==Originals26138768[i],"Original target/build profile mismatch");
            Require(result.Files[1].After=="d23a95d170c98458973281a24c15b06b5e1065bdab6eda0d533880f2ee0730cc","Unverified 26138768 font result");
        }
        if(build=="26151125") {
            Require(result.Guards[Guards[0]]=="0538c1abc7a51cae89ebfba154c2f84067f28c66393c50c7db213bbc0e900caa" &&
                    result.Guards[Guards[1]]=="56778d83a2fd108ebab4311a6639b9705750fb967705ff9a6852ef1c977f9d13","Guard/build profile mismatch");
            for(int i=0;i<paths.Length;i++) Require(result.Files[i].Before==Originals26138768[i],"Original target/build profile mismatch");
            Require(result.Files[1].After=="d23a95d170c98458973281a24c15b06b5e1065bdab6eda0d533880f2ee0730cc","Unverified 26151125 font result");
        }
        if(build=="26198171") {
            Require(result.Guards[Guards[0]]=="8d14bf5d963269952c29b380c1eeb79b3896d167c165a600cbda7549dfb048b7" &&
                    result.Guards[Guards[1]]=="0e733e4dce50c564916044fd4b99c3d58647bf275a56d0c538282ad615846574","Guard/build profile mismatch");
            for(int i=0;i<paths.Length;i++) Require(result.Files[i].Before==Originals26198171[i],"Original target/build profile mismatch");
            Require(result.Files[1].After=="d23a95d170c98458973281a24c15b06b5e1065bdab6eda0d533880f2ee0730cc","Unverified 26198171 font result");
        }
        if(format=="ckf-distribution-v2" && (build=="25889011" || build=="25951469" || build=="25964281" || Relocated(build))) Require(result.PartialImageNotice!=null,build+" images require partial status");
        if(format=="ckf-distribution-v2" && build!="25889011" && build!="25951469" && build!="25964281" && !Relocated(build)) {
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
