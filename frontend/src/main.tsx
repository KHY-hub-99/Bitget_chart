import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// index.html의 'root' 엘리먼트를 찾아 리액트 앱을 렌더링합니다.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
