// ====== Chatbot Toggle ======
const chatToggle = document.getElementById("chat-toggle");
const chatBox = document.getElementById("chatbot");
const closeChat = document.getElementById("close-chat");
const sendBtn = document.getElementById("send-btn");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");

// Open chatbot
chatToggle.addEventListener("click", () => {
  chatBox.style.display = "flex";
  chatToggle.style.display = "none";
});

// Close chatbot
closeChat.addEventListener("click", () => {
  chatBox.style.display = "none";
  chatToggle.style.display = "block";
});

// ====== Add message to chat window ======
function addMessage(sender, text) {
  const msgDiv = document.createElement("div");
  msgDiv.classList.add("message");
  msgDiv.innerHTML = `<strong>${sender}:</strong> ${text}`;
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ====== Send Message ======
async function sendMessage() {
  const message = chatInput.value.trim();
  if (!message) return;

  addMessage("You", message);
  chatInput.value = "";

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();
    addMessage("Bot", data.reply);
  } catch (error) {
    addMessage("Bot", "⚠️ Error: Unable to connect to the server.");
  }
}

// Send message on button click
sendBtn.addEventListener("click", sendMessage);

// Send message on Enter key
chatInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage();
});
