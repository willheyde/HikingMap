import { useState, useEffect, useMemo } from "react";
import { useUser } from "../context/UserContext";
import { listItems } from "../api/itemsService";
import { useNavigate } from "react-router-dom";
import ScrollBar from "../components/ScrollBar"; // Adjust path as needed

const QuickGearSetup = () => {
  // Destructure the context functions
  const { user, items: userItems, addItemsBatch, deleteItem } = useUser();
  const navigate = useNavigate();

  // --- DATA STATE ---
  const [catalog, setCatalog] = useState([]);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  
  // --- UI STATE ---
  const [activeCategory, setActiveCategory] = useState("All");
  const [selectedIds, setSelectedIds] = useState(new Set()); 
  const [isProcessing, setIsProcessing] = useState(false);

  // --- MODAL STATE ---
  const [itemToRemove, setItemToRemove] = useState(null); 
  const [showUnsavedModal, setShowUnsavedModal] = useState(false); 

  // 1. Fetch Catalog
  useEffect(() => {
    const fetchCatalog = async () => {
      try {
        const data = await listItems();
        setCatalog(data);
      } catch (err) {
        console.error("Failed to load item catalog:", err);
      } finally {
        setLoadingCatalog(false);
      }
    };
    fetchCatalog();
  }, []);

  // 2. Map item type to display category
  const getCategoryForItem = (itemType) => {
    const type = (itemType || "").toLowerCase();
    if (type.includes('backpack')) return "Backpacks";
    if (type.includes('shoe') || type.includes('footwear')) return "Shoes";
    if (type.includes('clothing') || type.includes('apparel')) return "Clothing";
    return "Items";
  };

  // 3. Derive Categories
  const categories = useMemo(() => {
    const categoriesSet = new Set(catalog.map(i => getCategoryForItem(i.item_type)));
    return ["All", ...Array.from(categoriesSet).sort()];
  }, [catalog]);

  // 4. Filter Items based on Tab
  const visibleItems = useMemo(() => {
    if (activeCategory === "All") return catalog;
    return catalog.filter(i => getCategoryForItem(i.item_type) === activeCategory);
  }, [activeCategory, catalog]);

  // 4. Helper: Check Ownership
  const isOwned = (catalogItemId) => {
    if (!userItems) return false;
    return userItems.some(uItem => uItem.id === catalogItemId);
  };

  // --- HANDLERS ---

  const handleItemClick = (item) => {
    if (isProcessing) return;

    if (isOwned(item.id)) {
      setItemToRemove(item);
    } else {
      const newSet = new Set(selectedIds);
      if (newSet.has(item.id)) {
        newSet.delete(item.id);
      } else {
        newSet.add(item.id);
      }
      setSelectedIds(newSet);
    }
  };

  const handleBulkAdd = async () => {
    if (!user || selectedIds.size === 0) return;
    setIsProcessing(true);
    
    const idsToSend = Array.from(selectedIds);

    try {
      await addItemsBatch(user.id, idsToSend);
      setSelectedIds(new Set());
      
      if (showUnsavedModal) {
        navigate("/map");
      }
    } catch (err) {
      console.error("Failed to bulk add items:", err);
    } finally {
      setIsProcessing(false);
      setShowUnsavedModal(false);
    }
  };

  const confirmRemove = async () => {
    if (!itemToRemove || !user) return;
    setIsProcessing(true);
    try {
      await deleteItem(user.id, itemToRemove.id);
      setItemToRemove(null);
    } catch (err) {
      console.error("Failed to remove item:", err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleNavigation = () => {
    if (selectedIds.size > 0) {
      setShowUnsavedModal(true);
    } else {
      navigate("/map");
    }
  };

  /* ================= VISUALS ================= */

  if (loadingCatalog) {
    return (
      <div className="h-screen bg-slate-900 text-white flex items-center justify-center">
        Loading Gear...
      </div>
    );
  }

  return (
    <div className="h-screen bg-slate-900 text-white flex flex-col relative overflow-hidden">
      
      {/* --- HEADER --- */}
      <div className="flex-none bg-slate-800/80 backdrop-blur-md border-b border-slate-700 z-20 shadow-md">
        <div className="p-4 md:p-6 flex justify-between items-center">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-blue-100">Gear Locker</h1>
            <p className="hidden md:block text-slate-400 text-sm mt-1">
              Select items to add. Green items are owned.
            </p>
          </div>

          <div className="flex items-center gap-4">
            {/* Weight Counter */}
            <div className="hidden md:flex flex-col items-end mr-4">
              <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Total Weight</span>
              <span className="text-lg font-mono text-blue-400">
                {userItems.reduce((acc, curr) => acc + (Number(curr.weight) || 0), 0).toFixed(2)} kg
              </span>
            </div>

            {/* Go To Map Button */}
            <button 
              onClick={handleNavigation}
              className="bg-slate-700 hover:bg-slate-600 text-white px-5 py-2 rounded-lg font-semibold transition-all flex items-center gap-2 border border-slate-600"
            >
              <span>Go to Map</span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"/>
              </svg>
            </button>
          </div>
        </div>

        {/* --- CATEGORY TABS --- */}
        <ScrollBar className="px-4 md:px-6 pb-0 !h-auto overflow-x-auto !overflow-y-hidden flex gap-2">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`
                whitespace-nowrap pb-3 px-2 border-b-2 text-sm font-medium transition-colors
                ${activeCategory === cat 
                  ? "border-blue-500 text-blue-400" 
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-600"}
              `}
            >
              {cat.replace('_', ' ')}
            </button>
          ))}
        </ScrollBar>
      </div>

      {/* --- GRID AREA --- */}
      <ScrollBar className="!h-auto flex-1 p-6 bg-slate-900 relative">
        <div className="max-w-7xl mx-auto pb-24">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
            {visibleItems.map((item) => {
              const owned = isOwned(item.id);
              const selected = selectedIds.has(item.id);

              return (
                <div 
                  key={item.id}
                  onClick={() => handleItemClick(item)}
                  className={`
                    relative group cursor-pointer rounded-xl transition-all duration-200 overflow-hidden border-2 flex flex-col
                    ${owned 
                      ? 'bg-green-900/20 border-green-600/50 shadow-[0_0_15px_rgba(34,197,94,0.1)]'
                      : selected
                        ? 'bg-blue-900/20 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.3)] scale-[1.02]'
                        : 'bg-slate-800 border-slate-700 hover:border-slate-500 hover:bg-slate-750'
                    }
                  `}
                >
                  {/* BADGES */}
                  {owned && (
                    <div className="absolute top-2 right-2 z-10 bg-green-600 text-white text-[10px] uppercase font-bold px-2 py-0.5 rounded-full shadow-sm flex items-center gap-1">
                      <span>✓</span> Owned
                    </div>
                  )}
                  {selected && !owned && (
                    <div className="absolute top-2 right-2 z-10 bg-blue-600 text-white text-[10px] uppercase font-bold px-2 py-0.5 rounded-full shadow-sm">
                      Selected
                    </div>
                  )}

                  {/* IMAGE */}
                  <div className={`h-32 w-full bg-slate-900 flex items-center justify-center overflow-hidden ${owned ? 'opacity-60 grayscale-[40%]' : ''}`}>
                    {item.image_url ? (
                      <img src={item.image_url} alt={item.name} className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-4xl">🏔️</span>
                    )}
                  </div>

                  {/* INFO */}
                  <div className="p-3 flex-1 flex flex-col justify-between">
                    <h3 className={`font-semibold text-sm leading-tight mb-1 ${owned ? 'text-green-200' : selected ? 'text-blue-200' : 'text-slate-200'}`}>
                      {item.name}
                    </h3>
                    <div className="flex justify-between items-end mt-2 text-xs font-mono text-slate-500">
                      <span>{Number(item.weight).toFixed(1)}kg</span>
                      <span className="text-slate-400">${item.cost}</span>
                    </div>
                  </div>
                  
                  {/* OVERLAYS */}
                  {owned && <div className="absolute inset-0 bg-green-900/10 pointer-events-none" />}
                  {selected && !owned && <div className="absolute inset-0 bg-blue-900/5 pointer-events-none" />}
                </div>
              );
            })}
          </div>
        </div>
      </ScrollBar>

      {/* --- FLOATING "ADD" BUTTON --- */}
      {selectedIds.size > 0 && (
        <div className="absolute bottom-8 left-0 right-0 flex justify-center z-30 pointer-events-none">
          <button
            onClick={handleBulkAdd}
            disabled={isProcessing}
            className="pointer-events-auto bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-full font-bold shadow-2xl shadow-blue-900/50 flex items-center gap-3 transform transition-all hover:-translate-y-1 active:scale-95 animate-in fade-in slide-in-from-bottom-4"
          >
            {isProcessing ? (
              <span>Saving...</span>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4"/>
                </svg>
                <span>Add {selectedIds.size} Item{selectedIds.size !== 1 && 's'}</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* --- DELETE CONFIRMATION MODAL --- */}
      {itemToRemove && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 border border-slate-600 rounded-2xl p-6 max-w-sm w-full shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-2">Remove Item?</h3>
            <p className="text-slate-300 mb-6">
              Remove <strong className="text-green-400">{itemToRemove.name}</strong> from your pack?
            </p>
            <div className="flex gap-3">
              <button 
                onClick={() => setItemToRemove(null)} 
                className="flex-1 px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white"
              >
                Cancel
              </button>
              <button 
                onClick={confirmRemove} 
                disabled={isProcessing} 
                className="flex-1 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold"
              >
                {isProcessing ? "..." : "Remove"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- UNSAVED CHANGES MODAL --- */}
      {showUnsavedModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-800 border border-blue-500/30 rounded-2xl p-6 max-w-md w-full shadow-2xl">
            <h3 className="text-xl font-bold text-white mb-2">Unsaved Gear Selected</h3>
            <p className="text-slate-300 mb-6">
              You have <strong className="text-blue-400">{selectedIds.size} items</strong> selected but not added to your inventory. 
              <br/><br/>
              Do you want to add them before leaving?
            </p>
            <div className="flex gap-3">
              <button 
                onClick={() => navigate("/map")}
                className="flex-1 px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors"
              >
                Discard & Leave
              </button>
              <button 
                onClick={handleBulkAdd}
                className="flex-1 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg"
              >
                Add & Leave
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QuickGearSetup;