import { useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";

import { useHikes } from "../context/HikeContext";
import { useInventory } from "../context/InventoryContext";
import { useUser } from "../context/UserContext";

const HikeDetail = () => {
  const { id } = useParams();

  const { selectedHike, fetchHikeById, loading } = useHikes();
  const { items } = useInventory();
  const { user } = useUser();

  // Fetch hike if user navigated directly
  useEffect(() => {
    if (!selectedHike || selectedHike.id !== id) {
      fetchHikeById(id);
    }
  }, [id]);

  // ---- Simple MVP Gear Rules ----
  const requiredGear = useMemo(() => {
    if (!selectedHike) return [];

    const gear = ["Backpack", "Water Bottle"];

    if (selectedHike.distance > 8) {
      gear.push("Hydration Pack");
    }

    if (selectedHike.elevation_gain > 2500) {
      gear.push("Trekking Poles");
    }

    if (selectedHike.max_altitude > 9000) {
      gear.push("Insulated Jacket");
    }

    return gear;
  }, [selectedHike]);

  const ownedGearNames = items.map((item) => item.name);

  const missingGear = requiredGear.filter(
    (gear) => !ownedGearNames.includes(gear)
  );

  const estimatedCost = missingGear.reduce((sum) => sum + 40, 0); // flat MVP estimate

  if (loading || !selectedHike) {
    return <p style={{ padding: "1rem" }}>Loading hike details...</p>;
  }

  return (
    <div style={{ padding: "2rem", maxWidth: "900px", margin: "auto" }}>
      {/* Hike Header */}
      <h1>{selectedHike.name}</h1>
      <p>{selectedHike.location}</p>

      {/* Stats */}
      <div style={{ display: "flex", gap: "2rem", margin: "1rem 0" }}>
        <div>
          <strong>Distance</strong>
          <p>{selectedHike.distance} miles</p>
        </div>
        <div>
          <strong>Elevation Gain</strong>
          <p>{selectedHike.elevation_gain} ft</p>
        </div>
        {selectedHike.max_altitude && (
          <div>
            <strong>Max Altitude</strong>
            <p>{selectedHike.max_altitude} ft</p>
          </div>
        )}
      </div>

      {/* Gear Section */}
      <hr />

      <h2>Required Gear</h2>
      <ul>
        {requiredGear.map((gear) => (
          <li key={gear}>{gear}</li>
        ))}
      </ul>

      <h2>Your Gear</h2>
      {items.length === 0 ? (
        <p>No gear added yet.</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item.id}>{item.name}</li>
          ))}
        </ul>
      )}

      {/* Missing Gear */}
      <hr />

      <h2>Missing Gear</h2>
      {missingGear.length === 0 ? (
        <p>✅ You have everything you need for this hike!</p>
      ) : (
        <>
          <ul>
            {missingGear.map((gear) => (
              <li key={gear}>{gear}</li>
            ))}
          </ul>

          <p>
            <strong>Estimated Cost:</strong> ${estimatedCost}
          </p>
        </>
      )}

      {/* Suitability */}
      <hr />

      <h2>Suitability</h2>
      {!user ? (
        <p>Create a profile to see personalized recommendations.</p>
      ) : missingGear.length === 0 ? (
        <p style={{ color: "green" }}>
          ✔ This hike is suitable with your current gear.
        </p>
      ) : (
        <p style={{ color: "orange" }}>
          ⚠ This hike requires additional gear.
        </p>
      )}
    </div>
  );
};

export default HikeDetail;
