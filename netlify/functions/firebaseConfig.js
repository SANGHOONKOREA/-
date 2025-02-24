// netlify/functions/firebaseConfig.js
// Netlify 서버리스 함수: 브라우저 대신 Firebase Config을 반환
// 실제 API 키는 Environment Variables로 저장

exports.handler = async (event) => {
  try {
    // (1) HTTP 메서드 체크
    if (event.httpMethod !== 'GET') {
      return {
        statusCode: 405,
        body: JSON.stringify({ error: 'Method not allowed' }),
      };
    }

    // (2) Netlify 환경변수에서 Firebase 설정 읽기
    const config = {
      apiKey: process.env.FIREBASE_API_KEY,
      authDomain: process.env.FIREBASE_AUTH_DOMAIN,
      databaseURL: process.env.FIREBASE_DB_URL,
      projectId: process.env.FIREBASE_PROJECT_ID,
      storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
      messagingSenderId: process.env.FIREBASE_SENDER_ID,
      appId: process.env.FIREBASE_APP_ID,
      measurementId: process.env.FIREBASE_MEASUREMENT_ID
    };
    // (config가 부족하면 Netlify Env에 추가)

    // (3) 반환
    return {
      statusCode: 200,
      body: JSON.stringify({ config }),
      headers: { 'Content-Type': 'application/json' }
    };

  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: err.message }),
    };
  }
};
