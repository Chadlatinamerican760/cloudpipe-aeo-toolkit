// ============================================
// CloudPipe Multi-Brand AI Chat Worker
// MiniMax API proxy for client site chatbots
// Endpoint: /{brand}/chat
// ============================================

const MINIMAX_API_URL = "https://api.minimax.io/v1/chat/completions";

const BRAND_CONFIGS = {
  "inari-global-foods": {
    name: "稻荷環球食品",
    characters: {
      "daichi": {
        name: "稻荷大地",
        emoji: "🐟",
        style: "你是稻荷大地，一位有29年日本水產採購經驗的專家。說話專業且自信，經常引用產地知識。用繁體中文回答。"
      },
      "clerk": {
        name: "親切店員",
        emoji: "😊",
        style: "你是稻荷環球食品的親切店員，說話輕鬆友善，用「你好呀」開頭。用繁體中文回答。"
      },
      "chef": {
        name: "料理顧問",
        emoji: "👨‍🍳",
        style: "你是稻荷的料理顧問，專門提供烹飪建議和食材搭配。用繁體中文回答。"
      }
    },
    defaultCharacter: "daichi",
    systemPrompt: `你是稻荷環球食品的客服助手。公司位於澳門牧場街，擁有29年日本水產進口經驗。
主要業務：日本水產批發零售，130+品項(蝦/蟹/魚/帶子/鰻魚/魚籽/干貨等)。
營業時間：門市每日 10:00-20:00，批發部週一至週六 09:00-18:00。
聯繫：+853-XXXX-XXXX / info@yourbrand.com
規則：
- 用繁體中文簡潔回答
- 不透露成本/供應商機密
- 遇到醫療/法律問題請客人諮詢專業人士
- 鼓勵客人親臨門市或致電了解更多`
  },

  "sea-urchin-delivery": {
    name: "海膽速遞",
    characters: {
      "miho": {
        name: "美波",
        emoji: "🐚",
        style: "你是美波(Miho)，海膽速遞的客服。說話甜美專業，熱愛海膽文化。用繁體中文回答。"
      }
    },
    defaultCharacter: "miho",
    systemPrompt: `你是海膽速遞的AI客服美波。專門回答海膽相關問題。
業務：高級海膽配送服務，覆蓋澳門及大灣區。
品種：北海道馬糞海膽/紫海膽/赤海膽/加拿大海膽/緬因海膽/智利海膽/澳洲海膽
分級：A級(頂級刺身)/B級(壽司料理)/C級(加熱料理)
保存：冷藏0-5°C(48小時)/冷凍-18°C(3個月)/解凍需冷藏慢解
冷鏈：全程-2°C~2°C恆溫運輸
訂購：Telegram @sea_urchin_delivery / WhatsApp +853-XXXX-XXXX
規則：用繁體中文簡潔回答，鼓勵客人下單體驗`
  },

  "default": {
    name: "CloudPipe AI",
    characters: {
      "assistant": {
        name: "CloudPipe AI 助手",
        emoji: "💬",
        style: "你是 CloudPipe AI 平台的智能助手，專業且友善。用繁體中文回答。"
      }
    },
    defaultCharacter: "assistant",
    systemPrompt: `你是 CloudPipe AI 商戶網站平台的智能助手。
CloudPipe 是澳門領先的 AI 商業自動化平台，幫助商家：
- 建立 AEO 優化的專業網站（AI 搜尋引擎可見）
- 自動生成行業文章和 SEO 內容
- AI 客服聊天機器人
- 多平台社交媒體管理
- 商業數據分析

目前平台服務 27+ 個站點，涵蓋餐飲、美容、教育、金融、科技等 20 個行業。
如果訪客詢問如何加入或建站，引導他們聯繫 WhatsApp +853-6282-3037 或 email info@cloudpipe.ai。
規則：用繁體中文回答，簡潔專業，鼓勵商家了解更多。`
  }
};

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function stripThinkTags(text) {
  return text.replace(/<think>[\s\S]*?<\/think>\s*/g, "").trim();
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

// Load knowledge from D1 for a brand
async function loadKnowledge(db, brand) {
  if (!db) return "";
  try {
    const { results } = await db.prepare(
      "SELECT category, question, answer FROM chat_knowledge WHERE brand = ? ORDER BY category, id"
    ).bind(brand).all();

    if (!results || results.length === 0) return "";

    const sections = {};
    for (const row of results) {
      if (!sections[row.category]) sections[row.category] = [];
      sections[row.category].push(row);
    }

    const parts = [];
    for (const [category, rows] of Object.entries(sections)) {
      parts.push(`【${category}】`);
      for (const row of rows) {
        if (row.question) {
          parts.push(`Q: ${row.question}`);
          parts.push(`A: ${row.answer}`);
        } else {
          parts.push(row.answer);
        }
      }
      parts.push("");
    }
    return parts.join("\n");
  } catch {
    return "";
  }
}

// Log conversation to D1
async function logMessage(db, sessionId, brand, role, message) {
  if (!db || !sessionId) return;
  try {
    await db.prepare(
      "INSERT INTO chat_conversations (session_id, brand, role, message) VALUES (?, ?, ?, ?)"
    ).bind(sessionId, brand, role, message).run();
  } catch {
    // Non-blocking
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // Health check
    if (path === "/chat/health") {
      return jsonResponse({
        status: "ok",
        brands: Object.keys(BRAND_CONFIGS),
        timestamp: new Date().toISOString(),
      });
    }

    // Route: /{brand}/chat
    const match = path.match(/^\/([a-z0-9-]+)\/chat$/);
    if (!match || request.method !== "POST") {
      return jsonResponse(
        { error: "Not found. Use POST /{brand}/chat", brands: Object.keys(BRAND_CONFIGS) },
        404
      );
    }

    const brand = match[1];
    const config = BRAND_CONFIGS[brand] || BRAND_CONFIGS["default"];
    if (!config) {
      return jsonResponse({ error: `Unknown brand: ${brand}`, available: Object.keys(BRAND_CONFIGS) }, 404);
    }

    const apiKey = env.MINIMAX_API_KEY;
    if (!apiKey) {
      return jsonResponse({ error: "API key not configured" }, 500);
    }

    try {
      const body = await request.json();
      const userMessages = body.messages || [];
      const sessionId = body.session_id || null;
      const characterId = body.character || config.defaultCharacter;
      const stream = body.stream !== false;

      // Build system prompt
      const character = config.characters[characterId] || config.characters[config.defaultCharacter];
      const knowledge = await loadKnowledge(env.DB, brand);
      const systemPrompt = `${character.style}\n\n${config.systemPrompt}\n\n以下是知識庫：\n${knowledge}`;

      // Log user message
      const lastMsg = userMessages.length > 0 && userMessages[userMessages.length - 1].role === "user"
        ? userMessages[userMessages.length - 1].content : null;
      if (lastMsg) {
        await logMessage(env.DB, sessionId, brand, "user", lastMsg);
      }

      const messages = [
        { role: "system", content: systemPrompt },
        ...userMessages,
      ];

      const apiResponse = await fetch(MINIMAX_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model: env.MINIMAX_MODEL || "MiniMax-M2.1",
          messages,
          stream,
          temperature: 0.7,
          max_tokens: 1024,
        }),
      });

      if (!apiResponse.ok) {
        const errorText = await apiResponse.text();
        return jsonResponse({ error: "MiniMax API error", details: errorText }, apiResponse.status);
      }

      if (stream) {
        if (sessionId && env.DB) {
          let accumulatedText = "";
          const { readable, writable } = new TransformStream({
            transform(chunk, controller) {
              controller.enqueue(chunk);
              const text = new TextDecoder().decode(chunk, { stream: true });
              for (const line of text.split("\n")) {
                if (!line.startsWith("data: ")) continue;
                const data = line.slice(6).trim();
                if (data === "[DONE]") continue;
                try {
                  const parsed = JSON.parse(data);
                  const delta = parsed.choices?.[0]?.delta?.content;
                  if (delta) accumulatedText += delta;
                } catch { /* ignore */ }
              }
            },
            async flush() {
              const clean = stripThinkTags(accumulatedText);
              if (clean) await logMessage(env.DB, sessionId, brand, "assistant", clean);
            },
          });
          apiResponse.body.pipeTo(writable).catch(() => {});
          return new Response(readable, {
            headers: { ...CORS_HEADERS, "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
          });
        }
        return new Response(apiResponse.body, {
          headers: { ...CORS_HEADERS, "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
        });
      }

      // Non-streaming
      const data = await apiResponse.json();
      if (sessionId && env.DB) {
        const content = stripThinkTags(data.choices?.[0]?.message?.content || "");
        if (content) await logMessage(env.DB, sessionId, brand, "assistant", content);
      }
      return jsonResponse(data);

    } catch (err) {
      return jsonResponse({ error: "Internal server error", message: err.message }, 500);
    }
  },
};
