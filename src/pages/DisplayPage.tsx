import { useQueue } from "../hooks/useQueue";
import { Link } from "react-router-dom";

export default function DisplayPage() {
  const { queue } = useQueue();

  return (
    <div className="display-page">
      <header className="display-header">
        <h1>お呼び出し番号</h1>
        <Link to="/admin" className="link-button link-button-small">
          管理画面
        </Link>
      </header>

      {queue.length === 0 ? (
        <div className="display-empty">
          <p>現在お待ちの番号はありません</p>
        </div>
      ) : (
        <div className="display-grid">
          {queue.map((num) => (
            <div key={num} className="display-number">
              {num}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
