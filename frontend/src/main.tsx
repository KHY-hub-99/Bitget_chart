import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./App.css";

// StrictMode를 제거하여 개발 모드에서도 한 번만 렌더링되게 설정
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
