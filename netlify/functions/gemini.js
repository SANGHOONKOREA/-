// netlify/functions/gemini.js
const fetch = require('node-fetch');

exports.handler = async (event) => {
  try {
    // 1) 메서드 체크
    if (event.httpMethod !== 'POST') {
      return {
        statusCode: 405,
        body: JSON.stringify({ error: 'Method not allowed, use POST' }),
      };
    }
    // 2) 요청 Body 파싱
    const body = JSON.parse(event.body || '{}');
    const contentText = body.contentText || '';
    if (!contentText) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'contentText is required' }),
      };
    }

    // 3) 환경변수에서 키 읽기
    const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
    if (!GEMINI_API_KEY) {
      return {
        statusCode: 500,
        body: JSON.stringify({ error: 'Missing GEMINI_API_KEY in environment' }),
      };
    }

    // 4) Google API 호출
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-pro-exp-02-05:generateContent?key=${GEMINI_API_KEY}`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        contents: [
          {
            role: 'user',
            parts: [
              {
                text:
                  "당신은 한국어 요약 도우미입니다. 40자 이내로 요약..." +
                  "\n\n" + contentText
              }
            ]
          }
        ]
      })
    });
    if (!resp.ok) {
      const eText = await resp.text();
      return {
        statusCode: resp.status,
        body: JSON.stringify({ error: 'Gemini API error', detail: eText }),
      };
    }

    const data = await resp.json();
    const summary = data?.candidates?.[0]?.content?.parts?.[0]?.text || '요약 실패';
    return {
      statusCode: 200,
      body: JSON.stringify({ summary }),
      headers: { 'Content-Type': 'application/json' }
    };

  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: err.message }),
    };
  }
};
