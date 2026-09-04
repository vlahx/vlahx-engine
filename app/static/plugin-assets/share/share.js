(() => {
  const urlEl = document.getElementById("share-url-field");
  const titleEl = document.getElementById("share-title-field");
  if (!urlEl || !titleEl) return;

  const getUrl = () => (urlEl.value ? urlEl.value.trim() : "");
  const getTitle = () => (titleEl.value ? titleEl.value.trim() : "");

  const nativeBtn = document.getElementById("share-native");
  const copyBtn = document.getElementById("share-copy");
  const toast = document.getElementById("share-toast");

  const showToast = (msg, isErr) => {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.toggle("share-toast--err", !!isErr);
    toast.classList.remove("d-none");
    window.setTimeout(() => toast.classList.add("d-none"), 3200);
  };

  const copiedEl = document.getElementById("share-copied-field");
  const getCopiedMsg = () => (copiedEl && copiedEl.value ? copiedEl.value : "Link copiat în clipboard!");

  const fallbackCopyTextToClipboard = (text) => {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      const ok = document.execCommand("copy");
      showToast(ok ? getCopiedMsg() : "Eroare la copiere.", !ok);
    } catch {
      showToast("Eroare la copiere.", true);
    }
    document.body.removeChild(textArea);
  };

  const copyLink = (url) => {
    if (!url) return showToast("Lipsește linkul de partajat.", true);
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard
        .writeText(url)
        .then(() => showToast(getCopiedMsg()))
        .catch(() => fallbackCopyTextToClipboard(url));
    } else {
      fallbackCopyTextToClipboard(url);
    }
  };

  nativeBtn?.addEventListener("click", () => {
    if (!navigator.share) return copyLink(getUrl());
    navigator
      .share({ title: getTitle(), url: getUrl() })
      .catch(() => copyLink(getUrl()));
  });

  copyBtn?.addEventListener("click", () => copyLink(getUrl()));

  const url = encodeURIComponent(getUrl());
  const title = encodeURIComponent(getTitle());
  const wa = document.getElementById("share-wa");
  const fb = document.getElementById("share-fb");
  const x = document.getElementById("share-x");
  const mail = document.getElementById("share-mail");
  if (wa) wa.href = `https://wa.me/?text=${title}%20${url}`;
  if (fb) fb.href = `https://www.facebook.com/sharer/sharer.php?u=${url}`;
  if (x) x.href = `https://twitter.com/intent/tweet?text=${title}&url=${url}`;
  if (mail) mail.href = `mailto:?subject=${title}&body=${url}`;
})();
