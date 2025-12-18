export default function CostBreakdownPanel({ costs }) {
  const total =
    (costs.travel ?? 0) +
    (costs.gear ?? 0) +
    (costs.fees ?? 0);

  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <h3 className="text-lg font-semibold mb-2">Estimated Cost</h3>

      <div className="text-sm space-y-1">
        <div className="flex justify-between">
          <span>🚗 Travel</span>
          <span>${costs.travel ?? 0}</span>
        </div>

        <div className="flex justify-between">
          <span>🎒 Missing Gear</span>
          <span>${costs.gear ?? 0}</span>
        </div>

        {costs.fees !== undefined && (
          <div className="flex justify-between">
            <span>🏞️ Fees</span>
            <span>${costs.fees}</span>
          </div>
        )}
      </div>

      <hr className="my-2" />

      <div className="flex justify-between font-bold">
        <span>Total</span>
        <span>${total}</span>
      </div>
    </div>
  );
}
