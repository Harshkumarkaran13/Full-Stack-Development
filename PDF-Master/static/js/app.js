document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("files");
  const drop = document.getElementById("drop");
  const list = document.getElementById("filelist");
  const manifest = document.getElementById("folder_manifest");
  if (!input || !drop || !list) return;

  const formatSize = (size) => `${(size / 1048576).toFixed(2)} MB`;
  const showFiles = () => {
    const files = Array.from(input.files || []);
    list.textContent = files.length
      ? `${files.length} file${files.length === 1 ? "" : "s"} selected · ${files.map((file) => `${file.name} (${formatSize(file.size)})`).join(" · ").slice(0, 900)}`
      : "";
    if (manifest) {
      manifest.value = JSON.stringify(files.map((file, index) => ({
        index,
        path: file.webkitRelativePath || file.name,
      })));
    }
  };

  input.addEventListener("change", showFiles);
  // Directory selection is intentionally browse-only so relative folder paths
  // are retained by the browser and nested files are not flattened on drop.
  if (!input.hasAttribute("webkitdirectory")) {
    ["dragenter", "dragover"].forEach((eventName) => {
      drop.addEventListener(eventName, (event) => {
        event.preventDefault();
        drop.classList.add("active");
      });
    });
    ["dragleave", "drop"].forEach((eventName) => {
      drop.addEventListener(eventName, (event) => {
        event.preventDefault();
        drop.classList.remove("active");
      });
    });
    drop.addEventListener("drop", (event) => {
      if (event.dataTransfer && event.dataTransfer.files.length) {
        input.files = event.dataTransfer.files;
        showFiles();
      }
    });
  }
});
