import React, { useEffect } from "react";

interface ToastProps {
  message: string;
  type: "success" | "error" | "info";
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({ message, type, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000); // 3초 뒤 자동 소멸
    return () => clearTimeout(timer);
  }, [onClose]);

  const colors = {
    success: "#00b561",
    error: "#eb4d4b",
    info: "#e3dc09",
  };

  return (
    <div
      style={{
        position: "fixed",
        top: "20px",
        right: "20px",
        padding: "12px 24px",
        backgroundColor: "#1e222d",
        color: colors[type],
        borderRadius: "8px",
        borderLeft: `4px solid ${colors[type]}`,
        boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
        zIndex: 100000,
        fontSize: "14px",
        fontWeight: "500",
        animation: "slideIn 0.3s ease-out forwards",
      }}
    >
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
      {type === "success" ? "🟢 " : type === "error" ? "🔴 " : "🟡 "}
      {message}
    </div>
  );
};
