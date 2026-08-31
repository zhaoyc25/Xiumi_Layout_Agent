const ui = {
  target: document.querySelector("#target"),
  file: document.querySelector("#file"),
  title: document.querySelector("#title"),
  desc: document.querySelector("#desc"),
  author: document.querySelector("#author"),
  link: document.querySelector("#link"),
  importButton: document.querySelector("#import"),
  status: document.querySelector("#status"),
};

let articleHtml = "";

function setStatus(message, warning = false) {
  ui.status.textContent = message;
  ui.status.className = warning ? "warning" : "";
}

function bodyFragment(documentNode) {
  const preferred = documentNode.querySelector("article, main, .rich_media_content");
  return (preferred || documentNode.body)?.innerHTML.trim() || "";
}

function localImageSources(html) {
  const documentNode = new DOMParser().parseFromString(html, "text/html");
  return [...documentNode.querySelectorAll("img[src]")]
    .map((image) => image.getAttribute("src")?.trim() || "")
    .filter((src) => src && !/^(https?:|data:)/i.test(src));
}

async function loadFile(file) {
  const text = await file.text();
  if (file.name.toLowerCase().endsWith(".json")) {
    const data = JSON.parse(text);
    if (typeof data.html !== "string" || !data.html.trim()) {
      throw new Error("JSON 中缺少非空的 html 字段。");
    }
    articleHtml = data.html.trim();
    ui.title.value = data.title || "";
    ui.desc.value = data.desc || "";
    ui.author.value = data.wxAuthor || "";
    ui.link.value = data.wxLink || "";
  } else {
    const documentNode = new DOMParser().parseFromString(text, "text/html");
    articleHtml = bodyFragment(documentNode);
    ui.title.value = documentNode.title || "";
    ui.desc.value = documentNode.querySelector('meta[name="description"]')?.content || "";
  }
  if (!articleHtml) throw new Error("文件中没有可导入的正文内容。");
  const badSources = localImageSources(articleHtml);
  if (badSources.length) {
    articleHtml = "";
    throw new Error(`发现 ${badSources.length} 张本地或相对路径图片，请先换成 HTTPS 或 data URL。示例：${badSources[0]}`);
  }
}

async function findEditors() {
  const tabs = await chrome.tabs.query({url: "https://mp.weixin.qq.com/cgi-bin/appmsg*"});
  ui.target.replaceChildren();
  for (const tab of tabs) {
    const option = document.createElement("option");
    option.value = String(tab.id);
    option.textContent = tab.title || `微信编辑页 ${tab.id}`;
    ui.target.append(option);
  }
  if (!tabs.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "未找到微信公众号图文编辑页";
    ui.target.append(option);
    setStatus("请先打开微信公众号的新建图文页面。", true);
  }
  ui.importButton.disabled = !tabs.length || !articleHtml;
}

function injectArticle(payload) {
  const fire = (element) => {
    element.dispatchEvent(new Event("input", {bubbles: true}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
  };
  const putValue = (selectors, value) => {
    if (!value) return;
    const element = selectors.map((selector) => document.querySelector(selector)).find(Boolean);
    if (!element) return;
    element.focus();
    element.value = value;
    fire(element);
  };

  putValue([".js_title_main .js_article_title"], payload.title);
  const titleEditor = document.querySelector(".title-editor-overlay .title-editor__input .ProseMirror");
  if (titleEditor && payload.title) {
    titleEditor.textContent = payload.title;
    fire(titleEditor);
  }
  putValue([".js_desc_area .js_desc"], payload.desc);
  putValue([".js_author_container .js_author"], payload.wxAuthor);

  let method = "";
  if (window.__MP_Editor_JSAPI__) {
    window.__MP_Editor_JSAPI__.invoke({
      apiName: "mp_editor_set_content",
      apiParam: {content: payload.html},
      sucCb: () => {},
      errCb: (error) => console.error("微信编辑器写入失败", error),
    });
    method = "jsapi";
  } else {
    const root = document.querySelector(".edui-editor-iframeholder .editor-v-root");
    const proseMirror = root?.shadowRoot?.querySelector(
      ".mock-iframe-document .mock-iframe-body .rich_media_content > .ProseMirror",
    );
    const iframeBody = document.querySelector(".edui-editor-iframeholder > iframe")?.contentWindow?.document?.body;
    const editor = proseMirror || iframeBody;
    if (!editor) throw new Error("没有找到微信正文编辑器，可能页面版本已变化。");
    editor.innerHTML = payload.html;
    fire(editor);
    method = proseMirror ? "prosemirror" : "iframe";
  }

  if (payload.wxLink) {
    const opener = document.querySelector(".js_url_area .js_article_url_allow_click");
    if (opener) {
      opener.click();
      setTimeout(() => {
        const input = document.querySelector(".popover-article-setting__content .js_url");
        if (input) {
          input.value = payload.wxLink;
          fire(input);
        }
      }, 500);
    }
  }
  return method;
}

ui.file.addEventListener("change", async () => {
  articleHtml = "";
  try {
    const file = ui.file.files?.[0];
    if (!file) return;
    await loadFile(file);
    setStatus("文件读取成功，可以导入。请确认标题和摘要。");
  } catch (error) {
    setStatus(error.message || String(error), true);
  }
  ui.importButton.disabled = !ui.target.value || !articleHtml;
});

ui.target.addEventListener("change", () => {
  ui.importButton.disabled = !ui.target.value || !articleHtml;
});

ui.importButton.addEventListener("click", async () => {
  try {
    ui.importButton.disabled = true;
    const results = await chrome.scripting.executeScript({
      target: {tabId: Number(ui.target.value)},
      world: "MAIN",
      func: injectArticle,
      args: [{
        title: ui.title.value.trim(),
        desc: ui.desc.value.trim(),
        html: articleHtml,
        wxAuthor: ui.author.value.trim(),
        wxLink: ui.link.value.trim(),
      }],
    });
    setStatus(`导入完成（${results[0]?.result || "editor"}）。请回到微信页面检查封面、图片和格式，然后手动保存并手机预览。`);
  } catch (error) {
    setStatus(`导入失败：${error.message || error}`, true);
  } finally {
    ui.importButton.disabled = !ui.target.value || !articleHtml;
  }
});

findEditors().catch((error) => setStatus(`查找微信页面失败：${error.message || error}`, true));
