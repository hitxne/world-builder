using System;
using System.IO;
using System.Runtime.InteropServices;

public static class WorkspaceFiles
{
    public static string Pick(bool save, string title, string extension)
    {
#if UNITY_EDITOR
        return save ? UnityEditor.EditorUtility.SaveFilePanel(title, "", "Untitled", extension)
            : UnityEditor.EditorUtility.OpenFilePanel(title, "", extension);
#elif UNITY_STANDALONE_WIN
        var dialog = new OpenFileName {
            size = Marshal.SizeOf(typeof(OpenFileName)),
            filter = extension.ToUpperInvariant() + " files\0*." + extension + "\0All files\0*.*\0\0",
            file = new string('\0', 32768), maxFile = 32768, title = title,
            defaultExtension = extension,
            flags = 0x00080000 | 0x00000008 | (save ? 0x00000002 : 0x00001000)
        };
        bool ok = save ? GetSaveFileName(ref dialog) : GetOpenFileName(ref dialog);
        if (ok) return dialog.file.Split('\0')[0];
        int error = CommDlgExtendedError();
        if (error != 0) throw new IOException("Windows file dialog failed: " + error);
        return "";
#else
        throw new PlatformNotSupportedException("File dialogs require Windows or Unity Editor.");
#endif
    }
#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct OpenFileName
    {
        public int size;
        public IntPtr owner, instance;
        public string filter, customFilter;
        public int maxCustomFilter, filterIndex;
        [MarshalAs(UnmanagedType.LPWStr)] public string file;
        public int maxFile;
        public string fileTitle;
        public int maxFileTitle;
        public string initialDirectory, title;
        public int flags;
        public short fileOffset, extensionOffset;
        public string defaultExtension;
        public IntPtr customData, hook;
        public string template;
        public IntPtr reserved;
        public int reserved2, flagsEx;
    }
    [DllImport("comdlg32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool GetOpenFileName(ref OpenFileName data);
    [DllImport("comdlg32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool GetSaveFileName(ref OpenFileName data);
    [DllImport("comdlg32.dll")] static extern int CommDlgExtendedError();
#endif
}
