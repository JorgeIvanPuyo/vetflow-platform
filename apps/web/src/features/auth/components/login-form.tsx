"use client";

import { Stethoscope } from "lucide-react";
import { FormEvent, useState } from "react";

import { useAuth } from "@/features/auth/auth-context";

type LoginState = {
  isSubmitting: boolean;
  errorMessage: string | null;
};

export function LoginForm() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [state, setState] = useState<LoginState>({
    isSubmitting: false,
    errorMessage: null,
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState({ isSubmitting: true, errorMessage: null });

    try {
      await login(email.trim(), password);
    } catch {
      setState({
        isSubmitting: false,
        errorMessage: "Credenciales inválidas",
      });
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-card" aria-labelledby="login-title">
        <div className="auth-brand">
          <span className="brand__mark brand__mark--large" aria-hidden="true">
            <Stethoscope size={28} />
          </span>
          <span>VetClinic</span>
        </div>

        <div>
          <p className="eyebrow">Acceso clínico</p>
          <h1 id="login-title">Iniciar sesión</h1>
          <p className="auth-card__copy">
            Ingresa con tu usuario autorizado para acceder a la clínica vinculada.
          </p>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="form-field">
            <span>Correo electrónico</span>
            <input
              autoComplete="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>

          <label className="form-field">
            <span>Contraseña</span>
            <input
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>

          {state.errorMessage ? <div className="error-state">{state.errorMessage}</div> : null}

          <button className="primary-button primary-button--full" disabled={state.isSubmitting} type="submit">
            {state.isSubmitting ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}
