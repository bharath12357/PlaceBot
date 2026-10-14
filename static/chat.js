(() => {
  "use strict";

  const TOPIC_LABELS = JSON.parse(document.getElementById("topic-data").textContent);

  const els = {
    list: document.getElementById("conversation-list"),
    messages: document.getElementById("messages"),
    form: document.getElementById("chat-form"),
    input: document.getElementById("input"),
    sendBtn: document.getElementById("send-btn"),
    newChat: document.getElementById("new-chat"),
    topicSelect: document.getElementById("topic-select"),
    title: document.getElementById("chat-title"),
    topic: document.getElementById("chat-topic"),
    menuBtn: document.getElementById("menu-btn"),
    overlay: document.getElementById("overlay"),
    sidebar: document.getElementById("sidebar"),
  };

  const SUGGESTIONS = [
    "Start interview",
    "Explain OOP pillars with an example",
    "What are SQL joins?",
    "How do I answer 'Tell me about yourself'?",
  ];

  let conversations = [];
  let currentId = null; // null = a new chat that is not saved yet
  let sending = false;

  // ------------------------------------------------------------- helpers
  async function api(path, options = {}) {
    const res = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (res.status === 401) {
      window.location.href = "/login";
      throw new Error("Please log in.");
    }
    let data = {};
    try { data = await res.json(); } catch (_) { /* empty body */ }
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  }

  function scrollToBottom() {
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function autoResize() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 140) + "px";
  }

  function setSending(value) {
    sending = value;
    els.sendBtn.disabled = value;
    els.input.disabled = value;
  }

  function closeSidebar() {
    els.sidebar.classList.remove("open");
    document.body.classList.remove("sidebar-open");
  }

  // --------------------------------------------------------- rendering
  function addMessage(kind, text) {
    const div = document.createElement("div");
    div.className = "msg " + kind;
    div.textContent = text; // textContent (not innerHTML) keeps this XSS-safe
    els.messages.appendChild(div);
    scrollToBottom();
    return div;
  }

  function showWelcome() {
    els.messages.innerHTML = "";
    const box = document.createElement("div");
    box.className = "welcome";
    box.id = "welcome";

    const h = document.createElement("h2");
    h.textContent = "Hi! I'm PlaceBot";
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Practice mock interviews or ask me to explain any concept.";
    const chips = document.createElement("div");
    chips.className = "chips";
    SUGGESTIONS.forEach((s) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = s;
      b.addEventListener("click", () => send(s));
      chips.appendChild(b);
    });

    box.append(h, p, chips);
    els.messages.appendChild(box);
  }

  function updateHeader() {
    const conv = conversations.find((c) => c.id === currentId);
    if (conv) {
      els.title.textContent = conv.title;
      els.topic.textContent = TOPIC_LABELS[conv.topic] || conv.topic;
    } else {
      els.title.textContent = "New chat";
      els.topic.textContent = TOPIC_LABELS[els.topicSelect.value] || "";
    }
  }

  function renderSidebar() {
    els.list.innerHTML = "";
    if (conversations.length === 0) {
      const empty = document.createElement("li");
      empty.className = "conv-empty";
      empty.textContent = "No saved chats yet.";
      els.list.appendChild(empty);
      return;
    }
    conversations.forEach((c) => {
      const li = document.createElement("li");
      li.className = "conv-item" + (c.id === currentId ? " active" : "");

      const open = document.createElement("button");
      open.type = "button";
      open.className = "conv-title";
      open.title = c.title;
      const name = document.createElement("span");
      name.className = "conv-name";
      name.textContent = c.title;
      const topic = document.createElement("span");
      topic.className = "conv-topic";
      topic.textContent = TOPIC_LABELS[c.topic] || c.topic;
      open.append(name, topic);
      open.addEventListener("click", () => selectConversation(c.id));

      const del = document.createElement("button");
      del.type = "button";
      del.className = "conv-del";
      del.setAttribute("aria-label", "Delete chat");
      del.textContent = "×";
      del.addEventListener("click", () => deleteConversation(c.id));

      li.append(open, del);
      els.list.appendChild(li);
    });
  }

  // ---------------------------------------------------------- actions
  async function loadConversations() {
    conversations = await api("/api/conversations");
    renderSidebar();
  }

  async function selectConversation(id) {
    try {
      const msgs = await api(`/api/conversations/${id}/messages`);
      currentId = id;
      els.messages.innerHTML = "";
      if (msgs.length === 0) showWelcome();
      msgs.forEach((m) => addMessage(m.role, m.content));
      renderSidebar();
      updateHeader();
      closeSidebar();
      els.input.focus();
    } catch (err) {
      addMessage("error", err.message);
    }
  }

  function startNewChat() {
    currentId = null;
    showWelcome();
    renderSidebar();
    updateHeader();
    closeSidebar();
    els.input.focus();
  }

  async function deleteConversation(id) {
    if (!window.confirm("Delete this chat permanently?")) return;
    try {
      await api(`/api/conversations/${id}`, { method: "DELETE" });
      conversations = conversations.filter((c) => c.id !== id);
      if (currentId === id) startNewChat();
      else renderSidebar();
    } catch (err) {
      window.alert(err.message);
    }
  }

  async function createConversation() {
    const conv = await api("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ topic: els.topicSelect.value }),
    });
    conversations.unshift(conv);
    currentId = conv.id;
    renderSidebar();
    updateHeader();
  }

  async function send(text) {
    text = text.trim();
    if (!text || sending) return;
    setSending(true);
    try {
      if (currentId === null) await createConversation();

      const welcome = document.getElementById("welcome");
      if (welcome) welcome.remove();

      addMessage("user", text);
      els.input.value = "";
      autoResize();
      const pending = addMessage("model typing", "Thinking...");

      try {
        const data = await api(`/api/conversations/${currentId}/chat`, {
          method: "POST",
          body: JSON.stringify({ message: text }),
        });
        pending.className = "msg model";
        pending.textContent = data.reply;

        const conv = conversations.find((c) => c.id === currentId);
        if (conv) conv.title = data.title;
        renderSidebar();
        updateHeader();
      } catch (err) {
        pending.className = "msg error";
        pending.textContent = err.message + " (This message was not saved. Please try again.)";
      }
      scrollToBottom();
    } catch (err) {
      addMessage("error", err.message);
    } finally {
      setSending(false);
      els.input.focus();
    }
  }

  // ----------------------------------------------------------- events
  els.form.addEventListener("submit", (e) => {
    e.preventDefault();
    send(els.input.value);
  });

  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(els.input.value);
    }
  });
  els.input.addEventListener("input", autoResize);

  els.newChat.addEventListener("click", startNewChat);
  els.topicSelect.addEventListener("change", () => {
    if (currentId === null) updateHeader();
  });

  els.menuBtn.addEventListener("click", () => {
    els.sidebar.classList.add("open");
    document.body.classList.add("sidebar-open");
  });
  els.overlay.addEventListener("click", closeSidebar);

  // ------------------------------------------------------------- start
  (async function init() {
    try {
      await loadConversations();
      if (conversations.length > 0) await selectConversation(conversations[0].id);
      else startNewChat();
    } catch (err) {
      showWelcome();
      addMessage("error", err.message);
    }
  })();
})();
