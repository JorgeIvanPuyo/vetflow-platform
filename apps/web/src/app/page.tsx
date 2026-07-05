import { HomeLandingGuard } from "@/features/auth/components/home-landing-guard";
import { DashboardHome } from "@/features/dashboard/components/dashboard-home";

export default function HomePage() {
  return (
    <HomeLandingGuard>
      <DashboardHome />
    </HomeLandingGuard>
  );
}
