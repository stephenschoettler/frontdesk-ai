console.log("App.js loaded, checking Vue...");

// Check if Vue is loaded
if (
  typeof Vue === "undefined" ||
  typeof Vue.createApp === "undefined" ||
  typeof axios === "undefined" ||
  typeof bootstrap === "undefined"
) {
  console.error(
    "Vue.js, Axios, or Bootstrap is not loaded. Please check your internet connection and try refreshing the page.",
  );
  document.getElementById("app").innerHTML =
    '<div class="alert alert-danger">Critical libraries (Vue.js, Axios, or Bootstrap) failed to load. Please check your internet connection and refresh the page.</div>';
} else {
  const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;

  Vue.createApp({
    setup() {
      console.log("Vue setup running...");
      const authToken = ref(localStorage.getItem("authToken"));
      const currentUser = ref(null);
      const currentView = ref(authToken.value ? "dashboard" : "login");

      const clients = ref([]);
      const filteredClients = ref([]);
      const selectedClients = ref([]);

      const allSelected = computed(
        () => selectedClients.value.length === filteredClients.value.length,
      );
      const selectedCallLogs = ref([]);
      const searchQuery = ref("");
      const filterStatus = ref("");
      const sortBy = ref("name");
      const currentPage = ref(1);
      const pageSize = ref(12);
      const showCreateModal = ref(false);
      const showEditModal = ref(false);
      const showBulkModal = ref(false);
      const showEditContactModal = ref(false);
      const showSettingsModal = ref(false);
      const showAuditLog = ref(false);
      const auditModal = ref(null);
      const openAuditLog = () => auditModal.value?.show();
      const closeAuditLog = () => auditModal.value?.hide();
      const systemPromptExpanded = ref(false);
      const saving = ref(false);
      const savingContact = ref(false);
      const selectedTemplate = ref("");
      const templates = ref({});

      const voicePresets = [
        { name: "Rachel (American, Calm, Pro)", id: "21m00Tcm4TlvDq8ikWAM" },
        { name: "Drew (American, News, Bold)", id: "29vD33N1CtxCmqQRPOHJ" },
        { name: "Clyde (Deep, Technical)", id: "2EiwWnXFnvU5JabPnv8n" },
        { name: "Mimi (Australian, Childish)", id: "zrHiDhphv9ZnVXBq79M6" },
        { name: "Fin (Irish, Energetic)", id: "D38z5RcWu1voky8WS1ja" },
        { name: "Antoni (American, Well-rounded)", id: "ErXwobaYiN019PkySvjV" },
        { name: "Thomas (American, Calm)", id: "GBv7mTt5Xyp17vW9q545" },
        { name: "Charlie (Australian, Casual)", id: "IKne3meq5aSn9XLyUdCD" },
        { name: "Emily (American, Calm)", id: "LcfcDJNUP1GQjkzn1xUU" },
        { name: "Elli (American, Emotional)", id: "MF3mGyEYCl7XYWbV9V6O" },
        { name: "Callum (American, Hoarse)", id: "N2lVS1w4Ejp13nTc3DX7" },
        { name: "Patrick (American, Shouty)", id: "ODq5zmih8GrVes37Dizd" },
        { name: "Harry (American, Anxiety)", id: "SOYHLrjzK2X1ezoPC6cr" },
        { name: "Liam (American, Neutral)", id: "TX3LPaxmHKxFdv7VOQHJ" },
        { name: "Dorothy (British, Pleasant)", id: "ThT5KcBeYPX3keUQqHPh" },
        { name: "Josh (American, Deep)", id: "TxGEqnHWrfWFTfGW9XjX" },
        { name: "Arnold (American, Nasal)", id: "VR6AewLTigWg4xSOukaG" },
        { name: "Charlotte (British, Seductive)", id: "XB0fDUnXU5powFXDhCwa" },
        { name: "Matilda (American, Warm)", id: "XrExE9yKIg1WjnnlVkGX" },
        { name: "James (Australian, Calm)", id: "ZQe5CZNOzWyzPSCn5a3c" },
        { name: "Joseph (British, News)", id: "Zlb1dXrM653N07WRdFW3" },
        { name: "Jeremy (American, Excited)", id: "bVMeCyTHy58xNoL34h3p" },
        { name: "Michael (American, Old)", id: "flq6f7yk4E4fJM5XTYuZ" },
        { name: "Ethan (American, Whisper)", id: "g5CIjZEefAph4nQFvHAz" },
        { name: "Gigi (American, Childish)", id: "jBpfuIE2acCO8z3wKNLl" },
        { name: "Freya (American, Overhyped)", id: "jsCqWAovK2LkecY7zXl4" },
        { name: "Santa Claus (Deep, Jolly)", id: "knrPHWnBmmDHMoiMeP3l" },
        { name: "Grace (American, Southern)", id: "oWAxZDx7w5VEj9dCyTzz" },
        { name: "Daniel (British, News)", id: "onwK4e9ZLuTAKqWW03F9" },
        { name: "Serena (American, Pleasant)", id: "pMsXgVXv3BLzUgSXRplE" },
        { name: "Adam (American, Deep)", id: "pNInz6obpgDQGcFmaJgB" },
        { name: "Nicole (American, Whisper)", id: "piTKgcLEGmPE4e6mEKli" },
        { name: "Bill (American, Trustworthy)", id: "pqHfZKP75CvOlQylNhV4" },
        { name: "Jessie (American, Raspy)", id: "t0jbNlBVZ17f02VDIeMI" },
        { name: "Sam (American, Raspy)", id: "yoZ06aMxZJJ28mfd3POQ" },
        { name: "Glinda (American, Witch)", id: "z9fAnlkpzviPz146aGWa" },
        { name: "Giovanni (Italian, Foreign)", id: "zcAOhNBS3c14rBihAFp1" },
        { name: "Domi (American, Strong)", id: "zRrTh6t1l6l36r8e9a2W" },
      ];

      const importFile = ref(null);
      const activeClientTab = ref("basic"); // Added for tabbed UI

      // SAFETY FIX: Handle corrupted storage gracefully
      let initialLogs = [];
      try {
        initialLogs = JSON.parse(localStorage.getItem("auditLogs") || "[]");
      } catch (e) {
        console.error("Resetting corrupted audit logs", e);
        initialLogs = [];
      }
      const auditLogs = ref(initialLogs);

      const activeTab = ref("clients");
      const contacts = ref([]);
      const selectedContacts = ref([]);
      const callLogs = ref([]);
      const selectedTranscript = ref(null);
      const transcriptExpanded = ref(false);
      const isLoading = ref(false);

      const contactSearchQuery = ref("");
      const logSearchQuery = ref("");
      const logFilterClient = ref("");
      const logFilterContact = ref("");

      // Inline editing state for contacts
      const editingContactPhone = ref(null);
      const tempContactName = ref("");

      // Theme management
      const themes = ref([]);
      const currentTheme = ref(
        localStorage.getItem("currentTheme") || "tokyo-night-default",
      );

      // Auth related state
      const authForm = ref({
        email: "",
        password: "",
      });
      const authError = ref(null);

      const clientForm = ref({
        name: "",
        cell: "",
        calendar_id: "",
        business_timezone: "America/Los_Angeles",
        business_start_hour: 9,
        business_end_hour: 17,
        llm_model: "openai/gpt-4o-mini",
        stt_model: "nova-2-phonecall",
        tts_model: "eleven_flash_v2_5",
        tts_voice_id: "21m00Tcm4TlvDq8ikWAM",
        initial_greeting: "",
        system_prompt: "",
        enabled_tools: [],
        enable_scheduling: false,
        enable_contact_memory: false,
        is_active: true, // Default active for new clients
      });

      const editingClient = ref(null);
      const editingContact = ref({
        phone: "",
        name: "",
      });

      const totalPages = computed(() =>
        Math.ceil(filteredClients.value.length / pageSize.value),
      );
      const visiblePages = computed(() => {
        const pages = [];
        const start = Math.max(1, currentPage.value - 2);
        const end = Math.min(totalPages.value, currentPage.value + 2);
        for (let i = start; i <= end; i++) {
          pages.push(i);
        }
        return pages;
      });

      const paginatedClients = computed(() => {
        const start = (currentPage.value - 1) * pageSize.value;
        const end = start + pageSize.value;
        return filteredClients.value.slice(start, end);
      });

      const filteredContacts = computed(() => {
        if (!contacts.value) return [];
        return contacts.value.filter((contact) => {
          const search = contactSearchQuery.value.toLowerCase();
          return (
            (contact.name && contact.name.toLowerCase().includes(search)) ||
            contact.phone.toLowerCase().includes(search)
          );
        });
      });

      const allContactsSelected = computed(() => {
        if (filteredContacts.value.length === 0) return false;
        return filteredContacts.value.every((contact) =>
          selectedContacts.value.includes(contact.phone),
        );
      });

      const contactsSelectIndeterminate = computed(() => {
        if (filteredContacts.value.length === 0) return false;
        const selectedCount = filteredContacts.value.filter((contact) =>
          selectedContacts.value.includes(contact.phone),
        ).length;
        return (
          selectedCount > 0 && selectedCount < filteredContacts.value.length
        );
      });

      const filteredCallLogs = computed(() => {
        if (!callLogs.value) return [];
        return callLogs.value.filter((log) => {
          const search = logSearchQuery.value.toLowerCase();
          const clientName = clients.value.find(
            (c) => c.id === logFilterClient.value,
          )?.name;
          const clientMatch =
            !logFilterClient.value ||
            (clientName && log.client_name === clientName);
          const contactMatch =
            !logFilterContact.value || log.phone === logFilterContact.value;

          const contact = contacts.value.find((c) => c.phone === log.phone);
          const contactName = contact ? contact.name : "";

          const searchMatch =
            !search ||
            (log.phone && log.phone.toLowerCase().includes(search)) ||
            (log.status && log.status.toLowerCase().includes(search)) ||
            (contactName && contactName.toLowerCase().includes(search));
          return clientMatch && searchMatch && contactMatch;
        });
      });

      const selectAllCallLogs = computed(() => {
        if (filteredCallLogs.value.length === 0) return false;
        return filteredCallLogs.value.every((log) =>
          selectedCallLogs.value.includes(log.id),
        );
      });

      const selectAllIndeterminate = computed(() => {
        if (filteredCallLogs.value.length === 0) return false;
        const selectedCount = filteredCallLogs.value.filter((log) =>
          selectedCallLogs.value.includes(log.id),
        ).length;
        return (
          selectedCount > 0 && selectedCount < filteredCallLogs.value.length
        );
      });

      // --- Auth Logic ---
      const setAuthToken = (token) => {
        authToken.value = token;
        if (token) {
          localStorage.setItem("authToken", token);
          axios.defaults.headers.common["Authorization"] = "Bearer " + token;
          try {
            const payload = JSON.parse(atob(token.split(".")[1]));
            currentUser.value = payload.email;
          } catch (e) {
            console.error("Error decoding token:", e);
            currentUser.value = "User";
          }
          currentView.value = "dashboard";
        } else {
          localStorage.removeItem("authToken");
          delete axios.defaults.headers.common["Authorization"];
          currentUser.value = null;
          currentView.value = "login";
        }
      };

      const login = async () => {
        authError.value = null;
        try {
          const response = await axios.post("/api/auth/login", authForm.value);
          setAuthToken(response.data.access_token);

          // --- THE RED CARPET ---
          // Check if the logged-in user is the admin
          if (currentUser.value === "admin@frontdesk.com") {
            console.log("Admin identified. Redirecting to Monitor.");
            window.location.href = "/static/monitor.html";
            return;
          }
          // ----------------------

          await loadClients();
        } catch (error) {
          console.error("Login failed:", error);
          authError.value =
            error.response?.data?.detail ||
            "Login failed. Please check your credentials.";
        }
      };

      const register = async () => {
        authError.value = null;
        try {
          const response = await axios.post(
            "/api/auth/register",
            authForm.value,
          );
          alert(response.data.message + ". Please login.");
          toggleAuthView();
        } catch (error) {
          console.error("Registration failed:", error);
          authError.value =
            error.response?.data?.detail || "Registration failed.";
        }
      };

      const logout = () => {
        setAuthToken(null);
        clients.value = [];
        contacts.value = [];
        callLogs.value = [];
        selectedTranscript.value = null;
        alert("You have been logged out.");
      };

      const toggleAuthView = () => {
        authError.value = null;
        authForm.value.password = "";
        currentView.value =
          currentView.value === "login" ? "register" : "login";
      };

      const loadClients = async () => {
        try {
          // Force network fetch to ensure fresh data
          // const localClients = localStorage.getItem("clients");
          // if (localClients) { ... }

          const response = await axios.get("/api/clients");

          clients.value = response.data.clients.map((c) => ({
            ...c,
            enabled_tools: c.enabled_tools || [],
            is_active: c.is_active !== undefined ? c.is_active : true, // Default to true if missing
          }));

          // Update Local Storage
          localStorage.setItem("clients", JSON.stringify(clients.value));

          filterClients();
        } catch (error) {
          console.error("Failed to load clients:", error);
        }
      };

      const loadTemplates = async () => {
        try {
          const response = await axios.get("/api/templates");
          templates.value = response.data;
        } catch (error) {
          console.error("Failed to load templates:", error);
        }
      };

      const importClients = (event) => {
        const file = event.target.files[0];

        if (file) {
          const reader = new FileReader();

          reader.onload = (e) => {
            try {
              const data = JSON.parse(e.target.result);

              clients.value = Array.isArray(data.clients) ? data.clients : data;

              localStorage.setItem("clients", JSON.stringify(clients.value));

              filterClients();

              alert("Clients imported successfully!");
            } catch (err) {
              alert("Invalid JSON file");
            }
          };

          reader.readAsText(file);
        }
      };

      const filterClients = () => {
        let filtered = clients.value.filter((client) => {
          const matchesSearch =
            client.name
              .toLowerCase()
              .includes(searchQuery.value.toLowerCase()) ||
            (client.cell && client.cell.includes(searchQuery.value));

          // UPDATED: Filter by is_active status
          const matchesStatus =
            !filterStatus.value ||
            (filterStatus.value === "active" && client.is_active) ||
            (filterStatus.value === "inactive" && !client.is_active);

          return matchesSearch && matchesStatus;
        });

        filtered.sort((a, b) => {
          if (sortBy.value === "name") {
            return a.name.localeCompare(b.name);
          } else {
            return new Date(b.created_at) - new Date(a.created_at);
          }
        });

        filteredClients.value = filtered;
        currentPage.value = 1;
      };

      const sortClients = () => {
        filterClients();
      };

      const editClient = (client) => {
        editingClient.value = client.id;
        const enabledTools = client.enabled_tools || [];
        clientForm.value = {
          ...client,
          enabled_tools: enabledTools,
          enable_scheduling: enabledTools.includes("book_appointment"),
          enable_contact_memory: enabledTools.includes("save_contact_name"),
          is_active: client.is_active !== undefined ? client.is_active : true,
        };
        activeClientTab.value = "basic";
        showEditModal.value = true;
      };

      const duplicateClient = (client) => {
        const duplicated = { ...client };
        delete duplicated.id;
        delete duplicated.created_at;
        duplicated.name += " (Copy)";
        const enabledTools = client.enabled_tools || [];
        duplicated.enabled_tools = enabledTools;
        duplicated.enable_scheduling =
          enabledTools.includes("book_appointment");
        duplicated.enable_contact_memory =
          enabledTools.includes("save_contact_name");
        duplicated.is_active = true; // Default copy to active
        editingClient.value = null;
        clientForm.value = duplicated;
        activeClientTab.value = "basic";
        showCreateModal.value = true;
      };

      const saveClient = async () => {
        saving.value = true;
        try {
          // Translate bundles to enabled_tools
          const payload = { ...clientForm.value };
          payload.enabled_tools = [];
          if (payload.enable_scheduling) {
            payload.enabled_tools.push(
              "get_available_slots",
              "book_appointment",
              "reschedule_appointment",
              "list_my_appointments",
              "cancel_appointment",
            );
          }
          if (payload.enable_contact_memory) {
            payload.enabled_tools.push("save_contact_name");
          }
          // Remove bundle fields from payload
          delete payload.enable_scheduling;
          delete payload.enable_contact_memory;

          let response;
          if (editingClient.value) {
            response = await axios.put(
              `/api/clients/${editingClient.value}`,
              payload,
            );
            const index = clients.value.findIndex(
              (c) => c.id === editingClient.value,
            );
            clients.value[index] = response.data;
            addAuditLog("update", `Updated client: ${response.data.name}`);
          } else {
            response = await axios.post("/api/clients", payload);
            clients.value.push(response.data);
            addAuditLog("create", `Created client: ${response.data.name}`);
          }
          closeModal();
          filterClients();
        } catch (error) {
          console.error("Failed to save client:", error);
          alert("Failed to save client");
        } finally {
          saving.value = false;
        }
      };

      const deleteClient = async (id) => {
        if (!confirm("Are you sure you want to delete this client?")) return;
        try {
          await axios.delete(`/api/clients/${id}`);
          clients.value = clients.value.filter((c) => c.id !== id);
          addAuditLog("delete", `Deleted client ID: ${id}`);
          filterClients();
        } catch (error) {
          console.error("Failed to delete client:", error);
          alert("Failed to delete client");
        }
      };

      const bulkDelete = async () => {
        if (
          !confirm(
            `Are you sure you want to delete ${selectedClients.value.length} clients?`,
          )
        )
          return;
        try {
          await Promise.all(
            selectedClients.value.map((id) =>
              axios.delete(`/api/clients/${id}`),
            ),
          );
          clients.value = clients.value.filter(
            (c) => !selectedClients.value.includes(c.id),
          );
          addAuditLog(
            "delete",
            `Bulk deleted ${selectedClients.value.length} clients`,
          );
          selectedClients.value = [];
          filterClients();
          showBulkModal.value = false;
        } catch (error) {
          console.error("Failed to bulk delete:", error);
          alert("Failed to bulk delete");
        }
      };

      const bulkUpdate = () => {
        alert("Bulk update not implemented yet");
      };

      // NEW: Toggle Client Status
      const toggleClientStatus = async (client) => {
        const newStatus = !client.is_active;
        const actionWord = newStatus ? "Enable" : "Disable";

        if (!confirm(`${actionWord} ${client.name}?`)) return;

        try {
          // Optimistic Update
          client.is_active = newStatus;

          await axios.put(`/api/clients/${client.id}`, {
            ...client,
            is_active: newStatus,
          });

          addAuditLog("update", `${actionWord}d client: ${client.name}`);
          filterClients(); // Re-apply filters
        } catch (error) {
          console.error("Failed to toggle status:", error);
          // Revert on failure
          client.is_active = !newStatus;
          alert(`Failed to ${actionWord.toLowerCase()} client.`);
        }
      };

      const deleteCallLogs = async () => {
        if (selectedCallLogs.value.length === 0) return;
        if (
          !confirm(
            `Are you sure you want to delete ${selectedCallLogs.value.length} call log(s)? This action cannot be undone.`,
          )
        )
          return;
        try {
          await Promise.all(
            selectedCallLogs.value.map((id) =>
              axios.delete(`/api/conversation-logs/${id}`),
            ),
          );
          callLogs.value = callLogs.value.filter(
            (log) => !selectedCallLogs.value.includes(log.id),
          );
          addAuditLog(
            "delete",
            `Deleted ${selectedCallLogs.value.length} call log(s)`,
          );
          selectedCallLogs.value = [];
        } catch (error) {
          console.error("Failed to delete call logs:", error);
          alert("Failed to delete call logs");
        }
      };

      const toggleSelectAllCallLogs = () => {
        if (selectAllCallLogs.value) {
          // Deselect all
          selectedCallLogs.value = selectedCallLogs.value.filter(
            (id) => !filteredCallLogs.value.some((log) => log.id === id),
          );
        } else {
          // Select all filtered logs
          const filteredIds = filteredCallLogs.value.map((log) => log.id);
          selectedCallLogs.value = [
            ...new Set([...selectedCallLogs.value, ...filteredIds]),
          ];
        }
      };

      const applyTemplate = () => {
        if (selectedTemplate.value && templates.value[selectedTemplate.value]) {
          const template = templates.value[selectedTemplate.value];
          clientForm.value.initial_greeting = template.initial_greeting;
          clientForm.value.system_prompt = template.system_prompt;
        }
      };

      const toggleBulkSelect = () => {
        if (selectedClients.value.length === filteredClients.value.length) {
          selectedClients.value = [];
        } else {
          selectedClients.value = filteredClients.value.map((c) => c.id);
        }
      };

      const bulkDuplicateClients = async () => {
        if (!confirm(`Duplicate ${selectedClients.value.length} clients?`))
          return;
        saving.value = true;
        try {
          await Promise.all(
            selectedClients.value.map((id) => {
              const client = clients.value.find((c) => c.id === id);
              if (client) duplicateClient(client);
            }),
          );
          selectedClients.value = [];
          await loadClients();
        } catch (e) {
          console.error("Bulk duplicate failed:", e);
        } finally {
          saving.value = false;
        }
      };

      const bulkDeleteClients = async () => {
        if (!confirm(`Delete ${selectedClients.value.length} clients?`)) return;
        try {
          await Promise.all(
            selectedClients.value.map((id) => deleteClient(id)),
          );
          selectedClients.value = [];
          await loadClients();
        } catch (e) {
          console.error("Bulk delete failed:", e);
        }
      };

      const toggleSelectAllContacts = () => {
        if (allContactsSelected.value) {
          // Deselect all
          selectedContacts.value = selectedContacts.value.filter(
            (phone) =>
              !filteredContacts.value.some(
                (contact) => contact.phone === phone,
              ),
          );
        } else {
          // Select all filtered contacts
          const filteredPhones = filteredContacts.value.map(
            (contact) => contact.phone,
          );
          selectedContacts.value = [
            ...new Set([...selectedContacts.value, ...filteredPhones]),
          ];
        }
      };

      const bulkDeleteContacts = async () => {
        if (!confirm(`Delete ${selectedContacts.value.length} contacts?`))
          return;
        try {
          await Promise.all(
            selectedContacts.value.map((phone) =>
              axios.delete(`/api/contacts/${encodeURIComponent(phone)}`),
            ),
          );
          // Update local state
          contacts.value = contacts.value.filter(
            (c) => !selectedContacts.value.includes(c.phone),
          );
          selectedContacts.value = [];
        } catch (error) {
          console.error("Bulk delete contacts failed:", error);
          alert("Failed to delete contacts.");
        }
      };

      const exportClients = () => {
        const dataStr = JSON.stringify(clients.value, null, 2);
        const dataUri =
          "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);
        const exportFileDefaultName = "clients_export.json";
        const linkElement = document.createElement("a");
        linkElement.setAttribute("href", dataUri);
        linkElement.setAttribute("download", exportFileDefaultName);
        linkElement.click();
      };

      const handleFileSelect = (event) => {
        importFile.value = event.target.files[0];
      };

      const executeImport = () => {
        if (!importFile.value) return;

        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const data = JSON.parse(e.target.result);
            const importedClients = Array.isArray(data.clients)
              ? data.clients
              : data;

            // Filter out duplicates by ID
            const existingIds = new Set(clients.value.map((c) => c.id));
            const newUniqueClients = importedClients.filter(
              (c) => !existingIds.has(c.id),
            );

            // Append new clients
            clients.value = [...clients.value, ...newUniqueClients];

            // Save to localStorage
            localStorage.setItem("clients", JSON.stringify(clients.value));

            // Filter and update UI
            filterClients();

            // Alert result
            alert(`Imported ${newUniqueClients.length} new clients.`);

            // Reset importFile
            importFile.value = null;
          } catch (err) {
            alert("Invalid JSON file");
          }
        };
        reader.readAsText(importFile.value);
      };

      const closeModal = () => {
        showCreateModal.value = false;
        showEditModal.value = false;
        editingClient.value = null;
        clientForm.value = {
          name: "",
          cell: "",
          calendar_id: "",
          business_timezone: "America/Los_Angeles",
          business_start_hour: 9,
          business_end_hour: 17,
          llm_model: "openai/gpt-4o-mini",
          stt_model: "nova-2-phonecall",
          tts_model: "eleven_flash_v2_5",
          tts_voice_id: "21m00Tcm4TlvDq8ikWAM",
          initial_greeting: "",
          system_prompt: "",
          enabled_tools: [],
          enable_scheduling: false,
          enable_contact_memory: false,
          is_active: true,
        };
        activeClientTab.value = "basic";
        selectedTemplate.value = "";
      };

      const addAuditLog = (type, action) => {
        const log = {
          id: Date.now(),
          type,
          action,
          timestamp: new Date().toISOString(),
        };
        auditLogs.value.unshift(log);
        if (auditLogs.value.length > 100) {
          auditLogs.value = auditLogs.value.slice(0, 100);
        }
        localStorage.setItem("auditLogs", JSON.stringify(auditLogs.value));
      };

      const formatDate = (dateStr) => {
        if (!dateStr) return "N/A";
        return new Date(dateStr).toLocaleString();
      };

      const formatHour = (hour) => {
        const period = hour >= 12 ? "PM" : "AM";
        const displayHour = hour % 12 || 12;
        return `${displayHour} ${period}`;
      };

      const formatDuration = (seconds) => {
        if (!seconds) return "0s";
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        if (m === 0) return `${s}s`;
        return `${m}m ${s}s`;
      };

      const jumpToContact = (phone) => {
        activeTab.value = "contacts";
        contactSearchQuery.value = phone;
      };

      const formatTimestamp = (timestampStr) => {
        if (!timestampStr) return "";
        try {
          const date = new Date(timestampStr);
          return date.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          });
        } catch (e) {
          return "";
        }
      };

      const formatToolName = (toolKey) => {
        const map = {
          get_available_slots: "Avail",
          book_appointment: "Book",
          reschedule_appointment: "Reschedule",
          list_my_appointments: "List Appts",
          save_contact_name: "Save Name",
          cancel_appointment: "Cancel",
        };
        return map[toolKey] || toolKey;
      };

      const getContactName = (phone) => {
        const contact = contacts.value.find((c) => c.phone === phone);
        // FIX: Return Name if exists, otherwise return the raw Phone Number
        return (contact && contact.name) ? contact.name : phone;
      };

      const loadContacts = async () => {
        if (contacts.value.length === 0) isLoading.value = true;
        try {
          const response = await axios.get("/api/contacts");
          contacts.value = response.data.contacts;
        } catch (error) {
          console.error("Failed to load contacts:", error);
        } finally {
          isLoading.value = false;
        }
      };

      const startInlineEdit = (contact) => {
        editingContactPhone.value = contact.phone;
        tempContactName.value = contact.name;
      };

      const cancelInlineEdit = () => {
        editingContactPhone.value = null;
        tempContactName.value = "";
      };

      const saveInlineEdit = async (contact) => {
        try {
          await axios.put(`/api/contacts/${contact.phone}`, {
            name: tempContactName.value,
          });
          await loadContacts(); // Refresh the contacts list
          cancelInlineEdit();
        } catch (error) {
          console.error("Failed to update contact name:", error);
          alert("Failed to update contact name. Please try again.");
        }
      };

      const editContact = (contact) => {
        editingContact.value = { ...contact };
        showEditContactModal.value = true;
      };

      const closeEditContactModal = () => {
        showEditContactModal.value = false;
        editingContact.value = { phone: "", name: "" };
      };

      const closeSettingsModal = () => {
        showSettingsModal.value = false;
      };

      const updateContactName = async () => {
        savingContact.value = true;
        try {
          await axios.put(`/api/contacts/${editingContact.value.phone}`, {
            name: editingContact.value.name,
          });
          await loadContacts(); // Refresh the contacts list
          closeEditContactModal();
        } catch (error) {
          console.error("Failed to update contact name:", error);
          alert("Failed to update contact name. Please try again.");
        } finally {
          savingContact.value = false;
        }
      };

      const deleteContact = async (phone) => {
        if (!confirm("Are you sure you want to delete this contact?")) return;
        try {
          await axios.delete(`/api/contacts/${encodeURIComponent(phone)}`);
          // Update local state instantly
          contacts.value = contacts.value.filter((c) => c.phone !== phone);
        } catch (error) {
          console.error("Failed to delete contact:", error);
          alert("Failed to delete contact.");
        }
      };

      const viewContactHistory = (contact) => {
        logFilterContact.value = contact.phone;
        logFilterClient.value = ""; // Clear client filter to ensure we see the logs
        activeTab.value = "logs";
      };

      const loadLogs = async () => {
        if (callLogs.value.length === 0) isLoading.value = true;
        try {
          const response = await axios.get("/api/conversation-logs");
          callLogs.value = response.data.conversation_logs;
        } catch (error) {
          console.error("Failed to load call logs:", error);
        } finally {
          isLoading.value = false;
        }
      };

      const selectTranscript = (log) => {
        // Pure copy, no manual greeting prepended
        selectedTranscript.value = JSON.parse(JSON.stringify(log));
      };

      const toggleTranscriptExpansion = () => {
        transcriptExpanded.value = !transcriptExpanded.value;
      };

      const toggleSystemPromptExpansion = () => {
        systemPromptExpanded.value = !systemPromptExpanded.value;
      };

      // Theme management functions
      const loadThemes = () => {
        // Load default themes inline to avoid fetch issues
        const defaultThemes = [
          {
            key: "tokyo-night-default",
            name: "Tokyo Night Default",
            data: {
              background: "#1a1b26",
              foreground: "#c0caf5",
              cursor: "#7aa2f7",
              selection: "#283457",
              ansi_colors: {
                black: "#15161E",
                red: "#F77693",
                green: "#9ECE6A",
                yellow: "#E0AF68",
                blue: "#7AA2F7",
                magenta: "#BB9AF7",
                cyan: "#7DCFFF",
                white: "#A9B1D6",
                bright_black: "#414868",
                bright_red: "#F77693",
                bright_green: "#9ECE6A",
                bright_yellow: "#E0AF68",
                bright_blue: "#7AA2F7",
                bright_magenta: "#BB9AF7",
                bright_cyan: "#7DCFFF",
                bright_white: "#C0CAF5",
              },
            },
          },
          {
            key: "tokyo-night-day",
            name: "Tokyo Night Day",
            data: {
              background: "#E2E2E7",
              foreground: "#3760BF",
              cursor: "#2E7DE9",
              selection: "#B7C1E3",
              ansi_colors: {
                black: "#B3B5B9",
                red: "#F52A65",
                green: "#587539",
                yellow: "#8C6C3E",
                blue: "#2E7DE9",
                magenta: "#9854F1",
                cyan: "#007197",
                white: "#6172B0",
                bright_black: "#A1A6C5",
                bright_red: "#F52A65",
                bright_green: "#587539",
                bright_yellow: "#8C6C3E",
                bright_blue: "#2E7DE9",
                bright_magenta: "#9854F1",
                bright_cyan: "#007197",
                bright_white: "#3760BF",
              },
            },
          },
          {
            key: "iceberg-dark",
            name: "Iceberg Dark",
            data: {
              description: "Dark background theme",
              background: "#161821",
              foreground: "#C7C9D1",
              cursor: "#89BFC3",
              selection: "#272C41",
              ansi_colors: {
                black: "#1E212B",
                red: "#E2777A",
                green: "#B6BA89",
                yellow: "#E2A677",
                blue: "#83A5AD",
                magenta: "#9F91A8",
                cyan: "#89BFC3",
                white: "#C7C9D1",
                bright_black: "#6B7089",
                bright_red: "#E98A8A",
                bright_green: "#C0CAF5",
                bright_yellow: "#E9B18A",
                bright_blue: "#91A9C6",
                bright_magenta: "#AD9FAD",
                bright_cyan: "#95C4CC",
                bright_white: "#D2D4DD",
              },
            },
          },
          {
            key: "iceberg-light",
            name: "Iceberg Light",
            data: {
              description: "Light background theme",
              background: "#E8E9EC",
              foreground: "#33374C",
              cursor: "#3F83A6",
              selection: "#CAD0D7",
              ansi_colors: {
                black: "#DCDFE7",
                red: "#CC517A",
                green: "#668E3D",
                yellow: "#C57339",
                blue: "#2D539E",
                magenta: "#7759B5",
                cyan: "#3F83A6",
                white: "#33374C",
                bright_black: "#838A96",
                bright_red: "#CC3768",
                bright_green: "#598030",
                bright_yellow: "#B6662D",
                bright_blue: "#22478E",
                bright_magenta: "#6845AD",
                bright_cyan: "#327698",
                bright_white: "#3D425E",
              },
            },
          },
        ];

        themes.value = defaultThemes;
        applyTheme(currentTheme.value);
      };

      // Helper function to get brightness of a hex color
      const getBrightness = (hexColor) => {
        // Remove # if present
        const color = hexColor.replace("#", "");
        // Convert to RGB
        const r = parseInt(color.substr(0, 2), 16);
        const g = parseInt(color.substr(2, 2), 16);
        const b = parseInt(color.substr(4, 2), 16);
        // Calculate brightness (YIQ formula)
        return (r * 299 + g * 587 + b * 114) / 1000;
      };

      const applyTheme = (themeKey) => {
        const theme = themes.value.find((t) => t.key === themeKey);
        if (!theme) {
          console.warn(`Theme ${themeKey} not found, using default`);
          return;
        }

        const root = document.documentElement;
        const themeData = theme.data;

        // Apply theme colors to CSS custom properties
        root.style.setProperty("--theme-bg", themeData.background || "#1a1b26");
        root.style.setProperty("--theme-fg", themeData.foreground || "#c0caf5");
        root.style.setProperty("--theme-cursor", themeData.cursor || "#7aa2f7");
        root.style.setProperty(
          "--theme-selection",
          themeData.selection || "#283457",
        );

        // Determine if this is a light theme and set appropriate muted text color
        const bgBrightness = getBrightness(themeData.background || "#1a1b26");
        const isLightTheme = bgBrightness > 128;
        const mutedColor = isLightTheme ? "#555" : "#888"; // Light gray for dark themes, dark gray for light themes
        root.style.setProperty("--theme-muted", mutedColor);

        // Apply ANSI colors
        const ansiColors = themeData.ansi_colors;
        if (ansiColors) {
          // Map ANSI colors to our theme variables
          root.style.setProperty(
            "--theme-bg-dark",
            ansiColors.black || "#16161e",
          );
          root.style.setProperty(
            "--theme-bg-mid",
            ansiColors.bright_black || "#2a2a37",
          );
          root.style.setProperty(
            "--theme-card-bg",
            ansiColors.black || "#16161e",
          );
          root.style.setProperty("--theme-blue", ansiColors.blue || "#7dcfff");
          root.style.setProperty(
            "--theme-purple",
            ansiColors.magenta || "#bb9af7",
          );
          root.style.setProperty(
            "--theme-green",
            ansiColors.green || "#9ece6a",
          );
          root.style.setProperty(
            "--theme-orange",
            ansiColors.yellow || "#e0af68",
          );
          root.style.setProperty("--theme-red", ansiColors.red || "#f7768e");
          root.style.setProperty(
            "--theme-comment",
            ansiColors.bright_black || "#565f89",
          );
          root.style.setProperty(
            "--theme-logo-white",
            ansiColors.bright_white || "#ffffff",
          );
        }

        // Set Default (Dark Mode) Border Variables
        root.style.setProperty("--theme-border-active", "2px");

        // Set Default (Dark Mode) Tools Variables
        root.style.setProperty("--theme-tools-bg", "transparent");
        root.style.setProperty("--theme-tools-border", "var(--theme-bg-mid)");
        root.style.setProperty("--theme-tools-label", "var(--theme-purple)");

        // Light theme overrides
        if (isLightTheme) {
          // Paper Fix
          root.style.setProperty("--theme-bg-dark", "#ffffff");
          root.style.setProperty("--theme-card-bg", "#ffffff");

          // Ink Fix
          root.style.setProperty("--theme-bg-mid", "#b4b9c9");

          // Dynamic Shadows & Stripes
          root.style.setProperty("--theme-table-stripe", "rgba(0, 0, 0, 0.03)");
          root.style.setProperty(
            "--theme-table-hover",
            "rgba(46, 125, 233, 0.1)",
          );
          root.style.setProperty("--theme-btn-glow", "rgba(0, 0, 0, 0.1)");
          root.style.setProperty("--theme-text-glow", "none");

          // Ambient Backgrounds
          root.style.setProperty(
            "--theme-gradient-1",
            "rgba(55, 96, 191, 0.15)",
          );
          root.style.setProperty(
            "--theme-gradient-2",
            "rgba(120, 117, 213, 0.15)",
          );

          // Border Thickness (Light Mode Override)
          root.style.setProperty("--theme-border-active", "3px");

          // Tools Container (Light Mode Override)
          root.style.setProperty(
            "--theme-tools-bg",
            "rgba(158, 206, 106, 0.15)",
          );
          root.style.setProperty(
            "--theme-tools-border",
            "rgba(88, 117, 57, 0.5)",
          );
          root.style.setProperty("--theme-tools-label", "#3c5220");
        }

        currentTheme.value = themeKey;
        localStorage.setItem("currentTheme", themeKey);
      };

      watch(activeTab, (newTab) => {
        if (newTab === "contacts") {
          loadContacts();
        } else if (newTab === "logs") {
          loadLogs();
          if (contacts.value.length === 0) {
            loadContacts();
          }
        }
      });

      watch([searchQuery, filterStatus], () => {
        filterClients();
      });

      // --- Axios Interceptor for 401 ---
      axios.interceptors.response.use(
        (response) => response,
        (error) => {
          if (
            error.response &&
            error.response.status === 401 &&
            authToken.value
          ) {
            alert("Session expired or unauthorized. Please log in again.");
            logout();
          }
          return Promise.reject(error);
        },
      );

      onMounted(() => {
        nextTick(() => {
          const modalEl = document.getElementById("auditLogModal");
          if (modalEl && typeof bootstrap !== "undefined") {
            try {
              auditModal.value = new bootstrap.Modal(modalEl);
            } catch (e) {
              console.error("Failed to initialize audit modal:", e);
            }
          }
        });
        // Load themes asynchronously without blocking app initialization
        setTimeout(() => {
          loadThemes();
          loadTemplates();
        }, 100);

        if (authToken.value) {
          setAuthToken(authToken.value);
          loadClients();
          if (activeTab.value === "contacts") {
            loadContacts();
          } else if (activeTab.value === "logs") {
            loadLogs();
          }
        } else {
          currentView.value = "login";

          nextTick(() => {
            const modalEl = document.getElementById("auditLogModal");
            if (modalEl && typeof bootstrap !== "undefined") {
              try {
                auditModal.value = new bootstrap.Modal(modalEl);
              } catch (e) {
                console.error("Failed to initialize audit modal:", e);
              }
            }
          });
        }
      });

      const hasScheduling = (client) => {
        return (
          client.enabled_tools?.some((tool) =>
            [
              "book_appointment",
              "get_available_slots",
              "reschedule_appointment",
              "list_my_appointments",
            ].includes(tool),
          ) || false
        );
      };

      const hasMemory = (client) => {
        return client.enabled_tools?.includes("save_contact_name") || false;
      };

      const getVoiceName = (voiceId) => {
        if (!voiceId) return "Unknown";
        const preset = voicePresets.find((v) => v.id === voiceId);
        return preset ? preset.name.split("(")[0].trim() : "Custom Voice";
      };

      const truncateId = (id) => {
        if (!id) return "";
        if (id.length <= 12) return id;
        return id.substring(0, 12) + "...";
      };

      const formatName = (name) => {
        if (!name) return "";
        return name
          .toLowerCase()
          .replace(/(?:^|\s|-)\S/g, (c) => c.toUpperCase())
          .replace(
            /\bMc[a-z]/g,
            (m) => m.substr(0, 2) + m.substr(2).toUpperCase(),
          )
          .replace(
            /\bO'[a-z]/g,
            (m) => m.substr(0, 2) + m.substr(2).toUpperCase(),
          );
      };

      return {
        formatName,
        clients,
        filteredClients: paginatedClients,
        selectedClients,
        selectedCallLogs,
        searchQuery,
        filterStatus,
        sortBy,
        currentPage,
        totalPages,
        visiblePages,
        showCreateModal,
        showEditModal,
        showBulkModal,
        showEditContactModal,
        showAuditLog,
        auditModal,
        openAuditLog,
        closeAuditLog,
        saving,
        savingContact,
        selectedTemplate,
        templates,
        auditLogs,
        clientForm,
        editingClient, // Added editingClient export
        editingContact,
        loadContacts,
        editContact,
        closeEditContactModal,
        showSettingsModal,
        closeSettingsModal,
        updateContactName,
        deleteContact,
        loadClients,
        filterClients,
        sortClients,
        editClient,
        duplicateClient,
        saveClient,
        deleteClient,
        bulkDelete,
        bulkUpdate,
        deleteCallLogs,
        toggleSelectAllCallLogs,
        selectAllCallLogs,
        selectAllIndeterminate,
        applyTemplate,
        exportClients,
        handleFileSelect,
        executeImport,
        importFile,
        toggleBulkSelect,
        bulkDuplicateClients,
        bulkDeleteClients,
        allSelected,
        closeModal,
        formatDate,
        formatHour,
        formatTimestamp,
        formatToolName,
        formatDuration, // Added formatDuration export
        jumpToContact, // Added jumpToContact export
        activeTab,
        isLoading,
        contacts,
        selectedContacts,
        callLogs,
        selectedTranscript,
        transcriptExpanded,
        contactSearchQuery,
        logSearchQuery,
        logFilterClient,
        logFilterContact,
        filteredContacts,
        allContactsSelected,
        contactsSelectIndeterminate,
        editingContactPhone,
        tempContactName,
        startInlineEdit,
        cancelInlineEdit,
        saveInlineEdit,
        toggleSelectAllContacts,
        bulkDeleteContacts,
        filteredCallLogs,
        toggleTranscriptExpansion,
        systemPromptExpanded,
        toggleSystemPromptExpansion,
        getContactName,
        viewContactHistory,
        selectTranscript,
        // Theme exports
        themes,
        currentTheme,
        applyTheme,
        templates,
        voicePresets,
        // Auth exports
        authToken,
        currentUser,
        currentView,
        authForm,
        authError,
        login,
        register,
        logout,
        toggleAuthView,
        hasScheduling,
        hasMemory,
        activeClientTab, // Added for Tab UI
        toggleClientStatus, // Added for activate/deactivate
        getVoiceName,
        truncateId,
      };
    },
  }).mount("#app");
}
