const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    backToLauncher: () => ipcRenderer.invoke('back-to-launcher')
});
