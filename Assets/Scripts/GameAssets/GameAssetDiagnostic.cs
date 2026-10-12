using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

// User-triggered, bounded metadata report. No binary resource content, absolute
// installation paths, game assets, credentials or executable code are exported.
public static class GameAssetDiagnostic
{
    [Serializable] public sealed class Report
    {
        public string generatedUtc = DateTime.UtcNow.ToString("O");
        public string reportVersion = "2";
        public string note = "Metadata only. Bounded scan, not a full installation inventory. No game resource bytes included.";
        public List<Game> games = new List<Game>();
    }
    [Serializable] public sealed class Game
    {
        public string name, error;
        public int visitedFolders, encounteredFiles;
        public bool truncated;
        public List<Count> extensions = new List<Count>();
        public List<Sample> samples = new List<Sample>();
    }
    [Serializable] public sealed class Count { public string extension; public int files; }
    [Serializable] public sealed class Sample
    {
        public string relativePath, format, error;
        public long sizeBytes;
        public int resourceCount, meshResourceCount;
        public string inspectionStatus;
        public int deletedResources, encryptedEntries;
        public List<string> meshNames = new List<string>();
        public List<Count> resourceTypes = new List<Count>();
    }
    public static Report Scan(string[] names, string[] paths)
    {
        if (names.Length != paths.Length) throw new ArgumentException("Game names/paths mismatch.");
        var report = new Report();
        for (int i = 0; i < paths.Length; i++) {
            var game = new Game { name = names[i] }; report.games.Add(game);
            if (!Directory.Exists(paths[i])) { game.error = "Installation folder not configured or unavailable."; continue; }
            string root = Path.GetFullPath(paths[i]).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            var counts = new Dictionary<string, int>(); var sampled = new Dictionary<string, int>();
            var pending = new Queue<string>(); pending.Enqueue(root);
            while (pending.Count > 0 && game.visitedFolders < 1500 && game.encounteredFiles < 50000) {
                string folder = pending.Dequeue(); game.visitedFolders++;
                try {
                    foreach (var path in Directory.EnumerateFiles(folder)) {
                        game.encounteredFiles++; string ext = Path.GetExtension(path).ToLowerInvariant();
                        if (ext == ".package" || ext == ".modelbin" || ext == ".swatchbin" || ext == ".zip" || ext == ".minizip" || ext == ".obj") {
                            counts[ext] = counts.TryGetValue(ext, out int count) ? count + 1 : 1;
                            string family = ext;
                            if (ext == ".package") {
                                string name = System.IO.Path.GetFileName(path).ToLowerInvariant();
                                family += name.Contains("fullbuild") ? ":full" : name.Contains("deltabuild") ? ":delta" : ":other";
                            }
                            if (ext == ".zip") {
                                string relative = path.Substring(root.Length).ToLowerInvariant().Replace('\\', '/');
                                family += relative.Contains("/cars/") ? ":cars" : relative.Contains("/tracks/") ? ":tracks" : ":other";
                            }
                            sampled.TryGetValue(family, out int n);
                            if (n < 8) { sampled[family] = n + 1; game.samples.Add(Inspect(path, root, ext)); }
                        }
                        if (game.encounteredFiles >= 50000) break;
                    }
                    foreach (var child in Directory.EnumerateDirectories(folder)) {
                        if ((File.GetAttributes(child) & FileAttributes.ReparsePoint) == 0 && pending.Count < 3000) pending.Enqueue(child);
                        else if (pending.Count >= 3000) game.truncated = true;
                    }
                } catch (UnauthorizedAccessException) { game.error = "Some folders were inaccessible."; }
                catch (IOException) { game.error = "Some folders could not be read."; }
            }
            game.truncated |= pending.Count > 0;
            foreach (var count in counts) game.extensions.Add(new Count { extension = count.Key, files = count.Value });
        }
        return report;
    }
    static Sample Inspect(string path, string root, string extension)
    {
        var sample = new Sample { relativePath = path.Substring(root.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar), format = extension };
        try {
            sample.sizeBytes = new FileInfo(path).Length;
            var types = new Dictionary<string, int>();
            if (extension == ".package") {
                var package = new SimsPackage(path); sample.resourceCount = package.Entries.Count;
                foreach (var entry in package.Entries) {
                    if (entry.IsDeleted) { sample.deletedResources++; continue; }
                    if (entry.Type == SimsPackage.Mlod) sample.meshResourceCount++;
                    string type = entry.Type.ToString("X8"); types[type] = types.TryGetValue(type, out int count) ? count + 1 : 1;
                }
            } else if (extension == ".modelbin" || extension == ".swatchbin") {
                var bundle = new ForzaBundle(path); sample.resourceCount = bundle.Blobs.Count;
                foreach (var blob in bundle.Blobs) {
                    if (blob.Tag == ForzaBundle.MeshTag) sample.meshResourceCount++;
                    string type = blob.Tag.ToString("X8") + ":" + blob.Major + "." + blob.Minor;
                    types[type] = types.TryGetValue(type, out int count) ? count + 1 : 1;
                }
            }
            else if (extension == ".zip") {
                var archive = GameArchiveDiagnostic.Inspect(path);
                sample.resourceCount = archive.Entries; sample.meshResourceCount = archive.MeshEntries;
                sample.encryptedEntries = archive.EncryptedEntries; sample.inspectionStatus = archive.Status; sample.meshNames = archive.MeshNames;
                foreach (var method in archive.Methods) types[method.Key] = method.Value;
            } else if (extension == ".minizip") {
                using (var stream = File.OpenRead(path)) using (var reader = new BinaryReader(stream)) {
                    if (stream.Length < 4) throw new FormatException("MiniZip file too short.");
                    sample.inspectionStatus = "MiniZip reader pending; container signature 0x" + reader.ReadUInt32().ToString("X8");
                }
            }
            foreach (var type in types) sample.resourceTypes.Add(new Count { extension = type.Key, files = type.Value });
        } catch (Exception e) {
            // Avoid recording OS exception messages that can reveal absolute paths.
            sample.error = e.GetType().Name + ": " + (e is NotSupportedException || e is FormatException ? e.Message : "Resource metadata inspection failed.");
        }
        return sample;
    }
}
