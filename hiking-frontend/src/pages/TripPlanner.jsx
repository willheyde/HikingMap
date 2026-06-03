import { useState, useRef, useEffect } from "react";

/* ─── Design tokens (matches app palette) ─────────────────────────────── */
const C = {
  page:        "#0d0a07",
  sidebar:     "#110d09",
  sidebarBorder:"#2a1c10",
  card:        "#1c1510",
  cardBorder:  "#4a3520",
  fieldBg:     "#241a10",
  fieldBorder: "#5a3e22",
  heading:     "#f0e6d0",
  subtext:     "#a08060",
  muted:       "#6a4e30",
  label:       "#b8906a",
  amber:       "#c17a2e",
  amberHover:  "#d98c38",
  amberText:   "#fff8ee",
  amberDim:    "rgba(193,122,46,0.12)",
  amberBorder: "rgba(193,122,46,0.35)",
  userBubble:  "#2a1e10",
  assistBg:    "transparent",
  divider:     "#2a1c10",
  inputBg:     "#1a1208",
  inputBorder: "#3a2810",
  scrollbar:   "#3a2510",
};

const serif = "Georgia, 'Times New Roman', serif";
const sans  = "'Trebuchet MS', 'Lucida Sans Unicode', sans-serif";
const mono  = "'Courier New', Courier, monospace";

/* ─── Mountain logo mark ─────────────────────────────────────────────── */
const Logo = ({ size = 22 }) => (
  <svg width={size} height={size * 0.85} viewBox="0 0 56 48" xmlns="http://www.w3.org/2000/svg" style={{ display: "block" }}>
    <polygon points="28,3 53,43 3,43" fill="none" stroke="#7a5030" strokeWidth="1.4" strokeLinejoin="round"/>
    <polygon points="14,43 28,16 42,43" fill="#2a1810" stroke="#c17a2e" strokeWidth="1" strokeLinejoin="round"/>
    <polygon points="28,3 33,11 23,11" fill="#c17a2e" opacity="0.8"/>
  </svg>
);

/* ─── Global styles + keyframes ─────────────────────────────────────── */
const GlobalStyles = () => (
  <style>{`
    @keyframes bounce {
      0%,60%,100% { transform: translateY(0); opacity:0.4; }
      30% { transform: translateY(-5px); opacity:1; }
    }
    @keyframes fadeIn {
      from { opacity:0; transform: translateY(6px); }
      to   { opacity:1; transform: translateY(0); }
    }
    @keyframes slideUp {
      from { opacity:0; transform: translateY(12px); }
      to   { opacity:1; transform: translateY(0); }
    }
    @keyframes huePulse {
      0%   { opacity: 0.55; transform: scale(1);    }
      50%  { opacity: 0.80; transform: scale(1.08); }
      100% { opacity: 0.55; transform: scale(1);    }
    }
    @keyframes hueShift {
      0%   { opacity: 0.30; transform: scale(1)    translateY(0px);  }
      50%  { opacity: 0.50; transform: scale(1.12) translateY(-12px);}
      100% { opacity: 0.30; transform: scale(1)    translateY(0px);  }
    }
    @keyframes hueOrbit {
      0%   { transform: translate(-50%,-50%) rotate(0deg)   scale(1);    }
      100% { transform: translate(-50%,-50%) rotate(360deg) scale(1);    }
    }
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: ${C.scrollbar}; border-radius: 2px; }
  `}</style>
);

/* ─── Ambient hue background ─────────────────────────────────────────── */
const AmbientHue = () => (
  <div style={{
    position: "absolute", inset: 0,
    pointerEvents: "none", overflow: "hidden",
    zIndex: 0,
  }}>
    {/* Core amber orb */}
    <div style={{
      position: "absolute",
      left: "50%", top: "48%",
      transform: "translate(-50%, -50%)",
      width: 520, height: 380,
      borderRadius: "50%",
      background: "radial-gradient(ellipse at center, rgba(193,122,46,0.22) 0%, rgba(193,122,46,0.08) 45%, transparent 72%)",
      animation: "huePulse 6s ease-in-out infinite",
    }} />
    {/* Warm outer bloom */}
    <div style={{
      position: "absolute",
      left: "50%", top: "50%",
      transform: "translate(-50%, -50%)",
      width: 820, height: 560,
      borderRadius: "50%",
      background: "radial-gradient(ellipse at center, rgba(160,80,20,0.10) 0%, rgba(100,40,10,0.05) 50%, transparent 75%)",
      animation: "hueShift 9s ease-in-out infinite",
    }} />
    {/* Cool deep-red counter-bloom for depth */}
    <div style={{
      position: "absolute",
      left: "50%", top: "60%",
      transform: "translate(-50%, -50%)",
      width: 600, height: 300,
      borderRadius: "50%",
      background: "radial-gradient(ellipse at center, rgba(80,20,5,0.18) 0%, transparent 70%)",
      animation: "huePulse 11s ease-in-out 2s infinite",
    }} />
    {/* Subtle top highlight */}
    <div style={{
      position: "absolute",
      left: "50%", top: "28%",
      transform: "translate(-50%, -50%)",
      width: 260, height: 180,
      borderRadius: "50%",
      background: "radial-gradient(ellipse at center, rgba(220,150,60,0.09) 0%, transparent 70%)",
      animation: "hueShift 7s ease-in-out 1s infinite",
    }} />
  </div>
);

/* ─── Typing indicator ───────────────────────────────────────────────── */
const TypingDots = () => (
  <div style={{ display: "flex", gap: 5, alignItems: "center", padding: "4px 0" }}>
    {[0,1,2].map(i => (
      <div key={i} style={{
        width: 6, height: 6, borderRadius: "50%",
        background: C.amber, opacity: 0.7,
        animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
      }}/>
    ))}
  </div>
);

/* ─── Suggestion chips ───────────────────────────────────────────────── */
const suggestions = [
  { icon: "🏔️", text: "Plan a 3-day Smoky Mountains trip" },
  { icon: "🌲", text: "Best gear for winter camping" },
  { icon: "🗺️", text: "Build a Pacific Crest Trail section" },
  { icon: "🎒", text: "What's missing from my gear list?" },
];

/* ─── Chat history items ─────────────────────────────────────────────── */
const history = [
  { id: 1, title: "Appalachian Trail Section Hike", date: "Today" },
  { id: 2, title: "Grand Teton 4-Day Loop", date: "Yesterday" },
  { id: 3, title: "Gear Check for Rainier Climb", date: "May 24" },
  { id: 4, title: "Yosemite JMT Planning", date: "May 20" },
  { id: 5, title: "Winter Camping Prep", date: "May 18" },
];

/* ─── Message bubble ─────────────────────────────────────────────────── */
const Message = ({ msg }) => {
  const isUser = msg.role === "user";
  return (
    <div style={{
      display: "flex",
      flexDirection: isUser ? "row-reverse" : "row",
      gap: 12,
      marginBottom: 24,
      animation: "slideUp 0.25s ease",
    }}>
      {/* Avatar */}
      {!isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: "50%",
          border: `1px solid ${C.amberBorder}`,
          background: C.fieldBg,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0, marginTop: 2,
        }}>
          <Logo size={16} />
        </div>
      )}

      <div style={{
        maxWidth: "72%",
        background: isUser ? C.userBubble : C.assistBg,
        border: isUser ? `1px solid ${C.fieldBorder}` : "none",
        borderRadius: isUser ? 16 : 0,
        borderTopRightRadius: isUser ? 4 : 0,
        padding: isUser ? "10px 16px" : "2px 0",
      }}>
        {/* Sender label for assistant */}
        {!isUser && (
          <div style={{
            fontFamily: sans, fontSize: 11, color: C.amber,
            letterSpacing: "0.08em", textTransform: "uppercase",
            marginBottom: 6, fontWeight: 600,
          }}>
            Trail AI
          </div>
        )}
        <div style={{
          fontFamily: serif,
          fontSize: 14.5,
          lineHeight: 1.75,
          color: isUser ? C.heading : "#d4c5a9",
          whiteSpace: "pre-wrap",
        }}>
          {msg.content}
        </div>

        {/* Action row for assistant messages */}
        {!isUser && (
          <div style={{ display: "flex", gap: 12, marginTop: 10, alignItems: "center" }}>
            {["copy","thumb-up","thumb-down","refresh"].map(action => (
              <button key={action}
                title={action}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  padding: "4px 6px", borderRadius: 6,
                  color: C.muted, fontSize: 13,
                  fontFamily: sans,
                  transition: "color 0.15s",
                }}
                onMouseEnter={e => e.currentTarget.style.color = C.label}
                onMouseLeave={e => e.currentTarget.style.color = C.muted}
              >
                {action === "copy" ? "⎘" : action === "thumb-up" ? "↑" : action === "thumb-down" ? "↓" : "↺"}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

/* ─── Initial welcome view ───────────────────────────────────────────── */
const WelcomeView = ({ onSend }) => (
  <div style={{
    flex: 1, display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center",
    padding: "40px 24px",
    animation: "fadeIn 0.4s ease",
  }}>
    {/* Hero mark */}
    <div style={{ marginBottom: 16 }}>
      <Logo size={48} />
    </div>

    <h1 style={{
      fontFamily: serif,
      fontSize: 32,
      fontWeight: 400,
      color: C.heading,
      textAlign: "center",
      margin: "0 0 10px",
      letterSpacing: "-0.02em",
    }}>
      Plan your next adventure
    </h1>

    <p style={{
      fontFamily: sans,
      fontSize: 14,
      color: C.subtext,
      textAlign: "center",
      margin: "0 0 40px",
      maxWidth: 380,
      lineHeight: 1.6,
    }}>
      AI-powered trip planning with your gear, your pace, your terrain.
    </p>

    {/* Suggestion chips */}
    <div style={{
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 10,
      maxWidth: 520,
      width: "100%",
    }}>
      {suggestions.map((s, i) => (
        <button key={i}
          onClick={() => onSend(s.text)}
          style={{
            background: C.fieldBg,
            border: `1px solid ${C.fieldBorder}`,
            borderRadius: 12,
            padding: "12px 16px",
            textAlign: "left",
            cursor: "pointer",
            transition: "all 0.15s",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = C.amber;
            e.currentTarget.style.background = C.amberDim;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = C.fieldBorder;
            e.currentTarget.style.background = C.fieldBg;
          }}
        >
          <div style={{ fontSize: 18, marginBottom: 5 }}>{s.icon}</div>
          <div style={{ fontFamily: sans, fontSize: 12.5, color: C.label, lineHeight: 1.5 }}>
            {s.text}
          </div>
        </button>
      ))}
    </div>
  </div>
);

/* ─── Main TripPlanner component ─────────────────────────────────────── */
export default function TripPlanner() {
  const [messages, setMessages]     = useState([]);
  const [input, setInput]           = useState("");
  const [isTyping, setIsTyping]     = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeChat, setActiveChat]   = useState(null);
  const [model, setModel]           = useState("Thinking");
  const endRef  = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const sendMessage = async (text) => {
    const content = (text || input).trim();
    if (!content) return;
    setInput("");

    const userMsg = { role: "user", content, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    // Simulate AI response
    await new Promise(r => setTimeout(r, 1400 + Math.random() * 800));

    const replies = [
      `Great choice! For that trip I'd recommend starting with checking your current gear loadout. Based on your profile you own the Black Diamond Cirque 45 — that's a solid pack for this route.\n\nHere's a suggested 3-day itinerary outline:\n\n**Day 1** — Trailhead to base camp (~8 miles, moderate)\n**Day 2** — Summit attempt and return (~6 miles, strenuous)\n**Day 3** — Scenic return route (~9 miles, easy)\n\nWant me to build out a full gear list optimized for this trip?`,
      `I've analyzed your gear locker and the route conditions. You're well-equipped for 3-season hiking, but for this specific trip I'd flag a few gaps:\n\n• You're missing a water filter — Sawyer Squeeze is 85g and fits your pack\n• No emergency beacon on record — highly recommended for remote routes\n• Your shelter is rated down to 20°F but overnight lows may reach 18°F\n\nShall I find gear suggestions that match your budget?`,
      `Perfect! I'll map that route and cross-reference it with your owned gear. The terrain is rated Class 2 with some Class 3 scrambling near the summit.\n\nEstimated total pack weight with your current gear: **4.2 kg** — within the ideal range for your distance.\n\nWould you like me to save this as a trip plan or keep refining the route?`,
    ];

    const assistMsg = {
      role: "assistant",
      content: replies[Math.floor(Math.random() * replies.length)],
      id: Date.now() + 1,
    };

    setMessages(prev => [...prev, assistMsg]);
    setIsTyping(false);
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      <GlobalStyles />
      <div style={{
      display: "flex",
      height: "100vh",
      width: "100vw",
      background: C.page,
      fontFamily: sans,
      overflow: "hidden",
    }}>

      {/* ── Sidebar ──────────────────────────────────────────────────── */}
      <aside style={{
        width: sidebarOpen ? 260 : 0,
        minWidth: sidebarOpen ? 260 : 0,
        background: C.sidebar,
        borderRight: `1px solid ${C.sidebarBorder}`,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        transition: "width 0.25s ease, min-width 0.25s ease",
      }}>
        <div style={{ padding: "16px 14px 12px", display: "flex", alignItems: "center", gap: 10 }}>
          <Logo size={20} />
          <span style={{ fontFamily: serif, fontSize: 15, color: C.heading, letterSpacing: "0.02em" }}>
            TripPlanner
          </span>
        </div>

        {/* New chat button */}
        <div style={{ padding: "0 10px 16px" }}>
          <button
            onClick={() => { setMessages([]); setActiveChat(null); }}
            style={{
              width: "100%",
              padding: "9px 14px",
              background: "none",
              border: `1px solid ${C.sidebarBorder}`,
              borderRadius: 10,
              cursor: "pointer",
              display: "flex", alignItems: "center", gap: 9,
              color: C.label,
              fontSize: 13,
              transition: "all 0.15s",
            }}
            onMouseEnter={e => { e.currentTarget.style.background = C.amberDim; e.currentTarget.style.borderColor = C.amberBorder; }}
            onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.borderColor = C.sidebarBorder; }}
          >
            <span style={{ fontSize: 16, lineHeight: 1 }}>＋</span>
            <span>New trip</span>
          </button>
        </div>

        <div style={{ padding: "0 14px 8px" }}>
          <span style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", letterSpacing: "1px" }}>
            Recent
          </span>
        </div>

        {/* History */}
        <div style={{ flex: 1, overflowY: "auto", padding: "0 8px" }}>
          {history.map(h => (
            <button key={h.id}
              onClick={() => setActiveChat(h.id)}
              style={{
                width: "100%",
                padding: "9px 10px",
                background: activeChat === h.id ? C.amberDim : "none",
                border: `1px solid ${activeChat === h.id ? C.amberBorder : "transparent"}`,
                borderRadius: 8,
                cursor: "pointer",
                textAlign: "left",
                marginBottom: 3,
                transition: "all 0.15s",
              }}
              onMouseEnter={e => { if (activeChat !== h.id) { e.currentTarget.style.background = C.fieldBg; }}}
              onMouseLeave={e => { if (activeChat !== h.id) { e.currentTarget.style.background = "none"; }}}
            >
              <div style={{ fontSize: 12.5, color: activeChat === h.id ? C.amberText : C.label, marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {h.title}
              </div>
              <div style={{ fontSize: 10.5, color: C.muted }}>{h.date}</div>
            </button>
          ))}
        </div>

        {/* User footer */}
        <div style={{
          padding: "12px 14px",
          borderTop: `1px solid ${C.sidebarBorder}`,
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <div style={{
            width: 28, height: 28, borderRadius: "50%",
            background: C.fieldBg, border: `1px solid ${C.amberBorder}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 11, color: C.amber, fontWeight: 700,
          }}>
            T
          </div>
          <div>
            <div style={{ fontSize: 12, color: C.heading }}>Tester</div>
            <div style={{ fontSize: 10.5, color: C.muted }}>3 items · 2.87 kg</div>
          </div>
        </div>
      </aside>

      {/* ── Main column ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
        <AmbientHue />

        {/* Top bar */}
        <header style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 20px",
          borderBottom: `1px solid ${C.sidebarBorder}`,
          background: "transparent",
          gap: 12,
          position: "relative", zIndex: 1,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              onClick={() => setSidebarOpen(o => !o)}
              style={{
                background: "none", border: "none", cursor: "pointer",
                padding: "6px 8px", borderRadius: 8,
                color: C.muted, fontSize: 18, lineHeight: 1,
                transition: "color 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.color = C.label}
              onMouseLeave={e => e.currentTarget.style.color = C.muted}
              title="Toggle sidebar"
            >
              ☰
            </button>

            {!sidebarOpen && (
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Logo size={18} />
                <span style={{ fontFamily: serif, fontSize: 14, color: C.heading }}>TripPlanner</span>
              </div>
            )}
          </div>

          {/* URL bar style indicator */}
          <div style={{
            flex: 1, maxWidth: 320,
            display: "flex", alignItems: "center",
            background: C.fieldBg,
            border: `1px solid ${C.fieldBorder}`,
            borderRadius: 20,
            padding: "5px 14px",
            gap: 7,
          }}>
            <span style={{ fontSize: 11, color: C.muted }}>🔒</span>
            <span style={{ fontFamily: mono, fontSize: 11.5, color: C.subtext, letterSpacing: "0.02em" }}>
              tripplanner.ai/chat
            </span>
          </div>

          {/* Model selector */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <select
              value={model}
              onChange={e => setModel(e.target.value)}
              style={{
                background: C.fieldBg,
                border: `1px solid ${C.fieldBorder}`,
                borderRadius: 20,
                padding: "5px 30px 5px 12px",
                color: C.label,
                fontFamily: sans,
                fontSize: 12.5,
                cursor: "pointer",
                appearance: "none",
                WebkitAppearance: "none",
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%236a4e30' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 10px center",
              }}
            >
              <option>Thinking</option>
              <option>Standard</option>
              <option>Lightweight</option>
            </select>

            <button
              onClick={() => window.location.href = "/map"}
              style={{
                background: C.amber,
                border: "none",
                borderRadius: 20,
                padding: "6px 16px",
                color: C.amberText,
                fontFamily: sans,
                fontSize: 12.5,
                cursor: "pointer",
                fontWeight: 600,
                letterSpacing: "0.03em",
                transition: "background 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.background = C.amberHover}
              onMouseLeave={e => e.currentTarget.style.background = C.amber}
            >
              View Map
            </button>
          </div>
        </header>

        {/* Messages or welcome */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: messages.length === 0 ? 0 : "32px 0",
          display: "flex",
          flexDirection: "column",
          position: "relative", zIndex: 1,
        }}>
          {messages.length === 0 ? (
            <WelcomeView onSend={sendMessage} />
          ) : (
            <div style={{ maxWidth: 680, width: "100%", margin: "0 auto", padding: "0 24px" }}>
              {messages.map(msg => (
                <Message key={msg.id} msg={msg} />
              ))}
              {isTyping && (
                <div style={{ display: "flex", gap: 12, marginBottom: 24, animation: "fadeIn 0.2s ease" }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: "50%",
                    border: `1px solid ${C.amberBorder}`,
                    background: C.fieldBg,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    flexShrink: 0,
                  }}>
                    <Logo size={16} />
                  </div>
                  <div style={{ padding: "8px 0" }}>
                    <div style={{ fontFamily: sans, fontSize: 11, color: C.amber, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8, fontWeight: 600 }}>
                      Trail AI
                    </div>
                    <TypingDots />
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}
        </div>

        {/* Input bar */}
        <div style={{
          padding: "16px 24px 20px",
          background: "transparent",
          borderTop: messages.length > 0 ? `1px solid ${C.sidebarBorder}` : "none",
          position: "relative", zIndex: 1,
        }}>
          <div style={{
            maxWidth: 680,
            margin: "0 auto",
            position: "relative",
          }}>
            {/* Attachment / extra actions row */}
            <div style={{
              background: C.inputBg,
              border: `1px solid ${C.inputBorder}`,
              borderRadius: 18,
              overflow: "hidden",
              transition: "border-color 0.15s",
            }}
              onFocusCapture={e => e.currentTarget.style.borderColor = C.amberBorder}
              onBlurCapture={e => e.currentTarget.style.borderColor = C.inputBorder}
            >
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Ask about trails, gear, or let me plan a trip…"
                rows={1}
                style={{
                  width: "100%",
                  background: "none",
                  border: "none",
                  outline: "none",
                  resize: "none",
                  padding: "16px 60px 16px 18px",
                  fontFamily: serif,
                  fontSize: 14,
                  color: C.heading,
                  lineHeight: 1.6,
                  boxSizing: "border-box",
                  caretColor: C.amber,
                  minHeight: 54,
                  maxHeight: 160,
                  overflowY: "auto",
                }}
                onInput={e => {
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
                }}
              />

              {/* Bottom action row inside input */}
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "8px 12px",
                borderTop: `1px solid ${C.inputBorder}`,
              }}>
                <div style={{ display: "flex", gap: 4 }}>
                  {[
                    { icon: "＋", label: "Attach" },
                    { icon: "📍", label: "Location" },
                    { icon: "🎒", label: "My gear" },
                  ].map(btn => (
                    <button key={btn.label}
                      title={btn.label}
                      style={{
                        background: "none", border: "none", cursor: "pointer",
                        padding: "4px 8px", borderRadius: 8,
                        color: C.muted, fontSize: 13,
                        fontFamily: sans,
                        display: "flex", alignItems: "center", gap: 5,
                        transition: "color 0.15s",
                      }}
                      onMouseEnter={e => e.currentTarget.style.color = C.label}
                      onMouseLeave={e => e.currentTarget.style.color = C.muted}
                    >
                      <span>{btn.icon}</span>
                      <span style={{ fontSize: 11 }}>{btn.label}</span>
                    </button>
                  ))}
                </div>

                {/* Send button */}
                <button
                  onClick={() => sendMessage()}
                  disabled={!input.trim() || isTyping}
                  style={{
                    background: input.trim() && !isTyping ? C.amber : C.fieldBg,
                    border: `1px solid ${input.trim() && !isTyping ? C.amber : C.fieldBorder}`,
                    borderRadius: 10,
                    width: 34, height: 34,
                    cursor: input.trim() && !isTyping ? "pointer" : "default",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    transition: "all 0.15s",
                    flexShrink: 0,
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 1L7 13M7 1L2 6M7 1L12 6"
                      stroke={input.trim() && !isTyping ? C.amberText : C.muted}
                      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
              </div>
            </div>

            <div style={{ textAlign: "center", marginTop: 8 }}>
              <span style={{ fontFamily: sans, fontSize: 10.5, color: C.muted, letterSpacing: "0.03em" }}>
                Trail AI can make mistakes. Verify conditions before heading out.
              </span>
            </div>
          </div>
        </div>
      </div>
      </div>
    </>
  );
}