import { useState } from "react";
import { useQueue } from "../hooks/useQueue";
import { Link } from "react-router-dom";

export default function AdminPage() {
  const { queue, addNumber, removeNumber, clearAll } = useQueue();
  const [input, setInput] = useState("");

  const handleAdd = () => {
    const num = parseInt(input, 10);
    if (!isNaN(num) && num > 0) {
      addNumber(num);
      setInput("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleAdd();
  };

  return (
    <div className="admin-page">
      <header className="admin-header">
        <h1>管理画面</h1>
        <Link to="/" className="link-button">
          表示画面を開く →
        </Link>
      </header>

      <div className="admin-input-section">
        <input
          type="number"
          min="1"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="番号を入力"
          className="number-input"
          autoFocus
        />
        <button onClick={handleAdd} className="btn btn-add">
          追加
        </button>
      </div>

      <div className="admin-queue-section">
        <div className="section-header">
          <h2>現在の待ち番号（{queue.length}件）</h2>
          {queue.length > 0 && (
            <button onClick={clearAll} className="btn btn-clear">
              すべてクリア
            </button>
          )}
        </div>

        {queue.length === 0 ? (
          <p className="empty-message">待ち番号はありません</p>
        ) : (
          <div className="admin-queue-list">
            {queue.map((num) => (
              <div key={num} className="admin-queue-item">
                <span className="admin-queue-number">{num}</span>
                <button
                  onClick={() => removeNumber(num)}
                  className="btn btn-remove"
                >
                  受渡済
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
