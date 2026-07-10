export default function MissingGearList({ items }) {
  if (!items || items.length === 0) {
    return (
      <div className="text-sage font-medium">
        ✅ You have all required gear!
      </div>
    );
  }

  return (
    <div>
      <h4 className="font-semibold mb-2">Missing Gear</h4>
      <ul className="list-disc list-inside text-sm">
        {items.map((item) => (
          <li key={item.id}>
            {item.name}{" "}
            {item.estimated_cost && (
              <span className="text-ink-muted">
                (${item.estimated_cost})
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
