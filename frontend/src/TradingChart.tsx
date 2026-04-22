import React from "react";

const TradingChart: React.FC<{ data: any }> = ({ data }) => {
  return (
    <div style={{ padding: "20px", color: "#4caf50" }}>
      <h3>✅ 프론트엔드 통신 테스트 성공!</h3>
      <p>
        백엔드로부터 <b>{data.candles?.length}</b>개의 캔들 데이터를 성공적으로
        전달받았습니다.
      </p>
    </div>
  );
};

export default TradingChart;
