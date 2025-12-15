import { useEffect, useState } from "react";
import { useUser } from "../context/UserContext";
import { useInventory } from "../context/InventoryContext";

const Profile = () => {
  const { user, editUser } = useUser();
  const {
    items,
    fetchUserItems,
    addItem,
    removeItem,
    loading,
  } = useInventory();

  const [newItemName, setNewItemName] = useState("");

  // Load inventory when profile loads
  useEffect(() => {
    if (user) {
      fetchUserItems(user.id);
    }
  }, [user]);

  if (!user) {
    return (
      <div style={{ padding: "2rem" }}>
        <h2>No User Loaded</h2>
        <p>Create or load a user to view your profile.</p>
      </div>
    );
  }

  const handleAddItem = async () => {
    if (!newItemName.trim()) return;

    await addItem(user.id, {
      name: newItemName,
    });

    setNewItemName("");
  };

  return (
    <div style={{ padding: "2rem", maxWidth: "800px", margin: "auto" }}>
      {/* Profile Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
        <img
          src={user.avatar_url || "https://via.placeholder.com/100"}
          alt="avatar"
          style={{ borderRadius: "50%", width: "100px" }}
        />
        <div>
          <h1>{user.name}</h1>
          <p>{user.home_location}</p>
        </div>
      </div>

      <hr style={{ margin: "2rem 0" }} />

      {/* Gear Inventory */}
      <h2>Your Gear</h2>

      {loading && <p>Loading inventory...</p>}

      {items.length === 0 ? (
        <p>No gear added yet.</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li
              key={item.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: "0.5rem",
              }}
            >
              <span>{item.name}</span>
              <button onClick={() => removeItem(user.id, item.id)}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Add Gear */}
      <div style={{ marginTop: "1.5rem" }}>
        <input
          type="text"
          placeholder="Add gear (e.g. Tent)"
          value={newItemName}
          onChange={(e) => setNewItemName(e.target.value)}
        />
        <button onClick={handleAddItem} style={{ marginLeft: "0.5rem" }}>
          Add
        </button>
      </div>
    </div>
  );
};

export default Profile;
