using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

[Serializable]
public sealed class WorkspaceDocument
{
    public int version = 1;
    public string title = "Untitled world";
    public List<WorkspaceProject> objects = new List<WorkspaceProject>();
    public static WorkspaceDocument Capture(Transform root, string title)
    {
        var document = new WorkspaceDocument { title = title };
        foreach (var identity in root.GetComponentsInChildren<WorkspaceIdentity>())
            if (identity.gameObject.activeInHierarchy && identity.GetComponent<MeshFilter>() != null)
                document.objects.Add(WorkspaceProject.Capture(identity.gameObject, identity.source ?? ""));
        return document;
    }
    public void Save(string path) => WorkspaceAtomicFile.Write(path, JsonUtility.ToJson(this, true));
    public static WorkspaceDocument Open(string path)
    {
        if (new FileInfo(path).Length > 128 * 1024 * 1024) throw new IOException("Project exceeds 128 MB safety limit.");
        var document = JsonUtility.FromJson<WorkspaceDocument>(File.ReadAllText(path));
        if (document == null || document.version != 1 || document.objects == null)
            throw new FormatException("Unsupported or invalid world project.");
        if (document.objects.Count > 2000) throw new FormatException("Project exceeds 2000-object safety limit.");
        return document;
    }
}

public static class WorkspaceAtomicFile
{
    public static void Write(string path, string content)=>WriteBytes(path,System.Text.Encoding.UTF8.GetBytes(content));
    public static void WriteBytes(string path,byte[] content)
    {
        string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try {
            using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            { stream.Write(content,0,content.Length); stream.Flush(true); }
            if (File.Exists(path)) File.Replace(temporary, path, path + ".bak");
            else File.Move(temporary, path);
        } finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }
}

// Bounded snapshot history is shared by all scene-edit operations. Mesh edits later
// need delta commands; this foundation avoids retaining destroyed Unity objects.
public sealed class WorkspaceHistory
{
    readonly List<string> states = new List<string>();
    int index = -1;
    public bool CanUndo => index > 0;
    public bool CanRedo => index + 1 < states.Count;
    public void Reset(string state) { states.Clear(); index = -1; Record(state); }
    public void Record(string state)
    {
        if (index >= 0 && states[index] == state) return;
        if (index + 1 < states.Count) states.RemoveRange(index + 1, states.Count - index - 1);
        states.Add(state); index++;
        long bytes = 0; foreach (string snapshot in states) bytes += snapshot.Length * 2L;
        while (states.Count > 1 && (states.Count > 20 || bytes > 32 * 1024 * 1024)) {
            bytes -= states[0].Length * 2L; states.RemoveAt(0); index--;
        }
    }
    public string Undo() { if (!CanUndo) return null; return states[--index]; }
    public string Redo() { if (!CanRedo) return null; return states[++index]; }
}
