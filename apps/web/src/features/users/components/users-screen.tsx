"use client";

import { Search, ShieldCheck, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { useCurrentUser } from "@/features/auth/current-user-context";
import { InviteUserModal } from "@/features/users/components/invite-user-modal";
import { listTenants, listUsers } from "@/features/users/services/users";
import { getApiErrorMessage } from "@/lib/api";
import type { AdminUser, AppRole, TenantOption } from "@/types/api";

const ROLE_LABELS: Record<AppRole, string> = {
  superadmin: "Superadmin",
  medico_veterinario: "Médico veterinario",
  contador: "Contador",
};

type StatusFilter = "all" | "active" | "inactive";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleDateString("es-PA", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function UsersScreen() {
  const router = useRouter();
  const { role, isLoading: isRoleLoading } = useCurrentUser();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [tenantFilter, setTenantFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isInviteOpen, setIsInviteOpen] = useState(false);

  const isSuperadmin = role === "superadmin";

  useEffect(() => {
    if (!isRoleLoading && role && !isSuperadmin) {
      router.replace("/");
    }
  }, [isRoleLoading, role, isSuperadmin, router]);

  const isActiveFilter = useMemo<boolean | undefined>(() => {
    if (statusFilter === "active") return true;
    if (statusFilter === "inactive") return false;
    return undefined;
  }, [statusFilter]);

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await listUsers({
        tenant_id: tenantFilter || undefined,
        is_active: isActiveFilter,
        search: search || undefined,
      });
      setUsers(response.data);
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [tenantFilter, isActiveFilter, search]);

  useEffect(() => {
    if (!isSuperadmin) return;
    void loadUsers();
  }, [isSuperadmin, loadUsers]);

  useEffect(() => {
    if (!isSuperadmin) return;
    listTenants()
      .then((response) => setTenants(response.data))
      .catch(() => setTenants([]));
  }, [isSuperadmin]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearch(searchInput.trim());
  }

  if (!isSuperadmin) {
    return null;
  }

  return (
    <div className="page-stack">
      <section className="screen-heading list-page__header">
        <div>
          <h1>
            <ShieldCheck aria-hidden="true" size={22} /> Usuarios
          </h1>
          <p>{users.length} usuarios</p>
        </div>
        <button
          className="primary-button"
          onClick={() => setIsInviteOpen(true)}
          type="button"
        >
          <UserPlus aria-hidden="true" size={18} /> Invitar usuario
        </button>
      </section>

      <section className="panel users-toolbar">
        <form className="search-form" onSubmit={handleSearch}>
          <label className="search-field">
            <Search size={18} />
            <input
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Buscar por nombre o correo..."
              value={searchInput}
            />
          </label>
          <button className="search-button" type="submit">
            Buscar
          </button>
        </form>

        <div className="users-filters">
          <label className="field">
            <span>Compañía</span>
            <select
              onChange={(event) => setTenantFilter(event.target.value)}
              value={tenantFilter}
            >
              <option value="">Todas</option>
              {tenants.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Estado</span>
            <select
              onChange={(event) =>
                setStatusFilter(event.target.value as StatusFilter)
              }
              value={statusFilter}
            >
              <option value="all">Todos</option>
              <option value="active">Activos</option>
              <option value="inactive">Inactivos</option>
            </select>
          </label>
        </div>
      </section>

      {errorMessage ? <div className="error-state">{errorMessage}</div> : null}

      {isLoading ? (
        <div className="empty-state">Cargando usuarios...</div>
      ) : users.length === 0 ? (
        <div className="empty-state">No se encontraron usuarios.</div>
      ) : (
        <section className="panel users-table-wrapper">
          <table className="users-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Correo</th>
                <th>Compañía</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Creado</th>
                <th>Actualizado</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.full_name}</td>
                  <td>{user.email}</td>
                  <td>{user.tenant_name}</td>
                  <td>{ROLE_LABELS[user.role] ?? user.role}</td>
                  <td>
                    <span
                      className={`badge ${
                        user.is_active ? "badge--success" : "badge--muted"
                      }`}
                    >
                      {user.is_active ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                  <td>{formatDate(user.created_at)}</td>
                  <td>{formatDate(user.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {isInviteOpen ? (
        <InviteUserModal
          tenants={tenants}
          onClose={() => setIsInviteOpen(false)}
          onInvited={() => {
            void loadUsers();
          }}
        />
      ) : null}
    </div>
  );
}
