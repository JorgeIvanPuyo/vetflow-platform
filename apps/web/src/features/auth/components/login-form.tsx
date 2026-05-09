"use client";

import { CheckCircle2, Eye, EyeOff, ShieldCheck, Stethoscope } from "lucide-react";
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
  const [showPassword, setShowPassword] = useState(false);
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
      <div className="auth-layout">
        <LoginBrandHeader />
        <LoginBrandPanel />
        <LoginFormCard
          email={email}
          errorMessage={state.errorMessage}
          isSubmitting={state.isSubmitting}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          onSubmit={handleSubmit}
          onTogglePassword={() => setShowPassword((current) => !current)}
          password={password}
          showPassword={showPassword}
        />
      </div>
    </main>
  );
}

function LoginBrandHeader() {
  return (
    <div className="auth-brand auth-brand--mobile" aria-label="VetClinic">
      <span className="brand__mark" aria-hidden="true">
        <Stethoscope size={22} />
      </span>
      <span>VetClinic</span>
    </div>
  );
}

function LoginBrandPanel() {
  return (
    <section className="auth-brand-panel" aria-label="Presentación de VetClinic">
      <div className="auth-brand auth-brand--panel">
        <span className="brand__mark brand__mark--large" aria-hidden="true">
          <Stethoscope size={28} />
        </span>
        <span>VetClinic</span>
      </div>

      <div className="auth-brand-panel__copy">
        <p className="eyebrow">Plataforma clínica</p>
        <h1>Operación veterinaria clara, segura y trazable.</h1>
        <p>
          Centraliza pacientes, consultas, agenda, seguimientos e inventario en
          una experiencia pensada para equipos clínicos.
        </p>
      </div>

      <div className="auth-value-list" aria-label="Beneficios de la plataforma">
        <span>
          <CheckCircle2 aria-hidden="true" size={16} />
          Historias clínicas ordenadas
        </span>
        <span>
          <ShieldCheck aria-hidden="true" size={16} />
          Acceso seguro por clínica
        </span>
      </div>
    </section>
  );
}

function LoginFormCard({
  email,
  errorMessage,
  isSubmitting,
  onEmailChange,
  onPasswordChange,
  onSubmit,
  onTogglePassword,
  password,
  showPassword,
}: {
  email: string;
  errorMessage: string | null;
  isSubmitting: boolean;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTogglePassword: () => void;
  password: string;
  showPassword: boolean;
}) {
  return (
    <section className="auth-card" aria-labelledby="login-title">
      <div>
        <p className="eyebrow">Acceso clínico</p>
        <h1 id="login-title">Iniciar sesión</h1>
        <p className="auth-card__copy">
          Ingresa con tu usuario autorizado para acceder a la clínica vinculada.
        </p>
      </div>

      <form className="auth-form" onSubmit={onSubmit}>
        <label className="form-field">
          <span>Correo electrónico</span>
          <input
            autoComplete="email"
            onChange={(event) => onEmailChange(event.target.value)}
            required
            type="email"
            value={email}
          />
        </label>

        <label className="form-field">
          <span>Contraseña</span>
          <span className="password-field">
            <input
              autoComplete="current-password"
              onChange={(event) => onPasswordChange(event.target.value)}
              required
              type={showPassword ? "text" : "password"}
              value={password}
            />
            <button
              aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              className="password-toggle"
              onClick={onTogglePassword}
              type="button"
            >
              {showPassword ? (
                <EyeOff aria-hidden="true" size={19} />
              ) : (
                <Eye aria-hidden="true" size={19} />
              )}
            </button>
          </span>
        </label>

        <LoginSupportActions />

        {errorMessage ? <div className="error-state">{errorMessage}</div> : null}

        <button className="primary-button primary-button--full" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </section>
  );
}

function LoginSupportActions() {
  return (
    <div className="auth-support-actions">
      <span>¿Olvidaste tu contraseña?</span>
      <span>Solicita ayuda al administrador de tu clínica.</span>
    </div>
  );
}
