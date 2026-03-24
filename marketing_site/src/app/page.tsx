import Image from "next/image";
import {
  Search,
  Globe,
  Sparkles,
  BarChart3,
  Link2,
  Tag,
  Bell,
  RefreshCw,
  Users,
  Building2,
  Check,
  Phone,
  MapPin,
  Mail,
  ArrowRight,
  TrendingUp,
  FolderKanban,
  ThumbsUp,
  KeyRound,
} from "lucide-react";

const SIGNUP = "https://app.limeclicks.com/signup";
const SIGNIN = "https://app.limeclicks.com/signin";

export default function Home() {
  return (
    <main className="overflow-hidden">
      {/* Navigation */}
      <nav className="bg-[#1a1a2e] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            <Image
              src="/images/logo.png"
              alt="LimeClicks"
              width={180}
              height={40}
              className="h-10 w-auto"
            />
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="hover:text-[#a29bfe] transition">
                Features
              </a>
              <a href="#about" className="hover:text-[#a29bfe] transition">
                About
              </a>
              <a href="#pricing" className="hover:text-[#a29bfe] transition">
                Pricing
              </a>
              <a href="#contact" className="hover:text-[#a29bfe] transition">
                Contact
              </a>
              <a
                href={SIGNIN}
                className="hover:text-[#a29bfe] transition font-medium"
              >
                Login
              </a>
              <a
                href={SIGNUP}
                className="bg-[#6c5ce7] hover:bg-[#5a4bd1] px-6 py-2.5 rounded-lg font-medium transition"
              >
                Register
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="bg-[#1a1a2e] text-white pt-16 pb-24 relative">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight">
                Monitor Your
                <br />
                <span className="text-[#6c5ce7]">Google Search Rankings</span>
              </h1>
              <p className="mt-6 text-lg text-gray-300 max-w-lg">
                Elevate your business using improved SEO insights. Track
                keywords, analyze competitors, and grow your organic traffic.
              </p>
              <div className="mt-8 flex flex-wrap gap-4">
                <a
                  href={SIGNUP}
                  className="bg-[#6c5ce7] hover:bg-[#5a4bd1] px-8 py-3.5 rounded-lg font-semibold text-lg transition inline-flex items-center gap-2"
                >
                  Get Started Free <ArrowRight className="w-5 h-5" />
                </a>
                <a
                  href={SIGNIN}
                  className="border border-white/30 hover:border-white/60 px-8 py-3.5 rounded-lg font-semibold text-lg transition"
                >
                  Sign In
                </a>
              </div>
            </div>
            <div className="relative">
              <Image
                src="/images/banner.png"
                alt="LimeClicks Dashboard"
                width={700}
                height={500}
                className="w-full h-auto"
                priority
              />
            </div>
          </div>
        </div>
      </section>

      {/* Features Cards */}
      <section id="features" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold">
              Elevate your business using
              <br />
              improved <span className="text-[#6c5ce7]">SEO insights</span>.
            </h2>
            <p className="mt-4 text-gray-600 max-w-2xl mx-auto">
              Navigating the realm of SEO can frequently appear as enigmatic as
              a black box when it comes to gauging results. Our goal is to bring
              transparency to your marketing achievements.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            <FeatureCard
              icon={<Search className="w-8 h-8" />}
              title="Track your keywords"
              description="Gain a comprehensive overview of your entire website"
            />
            <FeatureCard
              icon={<Sparkles className="w-8 h-8" />}
              title="Discover new keywords"
              description="Our tools will help you find and focus on high volume keywords"
            />
            <FeatureCard
              icon={<BarChart3 className="w-8 h-8" />}
              title="Get ranking reports"
              description="Stay informed at all times. Receive customized reports."
            />
            <FeatureCard
              icon={<Globe className="w-8 h-8" />}
              title="Competitor Analysis"
              description="Find out your competitors and automates a detailed analysis for you to be a step ahead."
            />
            <FeatureCard
              icon={<Link2 className="w-8 h-8" />}
              title="Backlinks Analysis"
              description="Unlock Backlink Insights for Enhanced SEO Performance and Rankings with LimeClicks."
            />
            <FeatureCard
              icon={<Tag className="w-8 h-8" />}
              title="100% White Label"
              description="Contact our support team to access a fully white-labeled solution tailored for agencies."
            />
          </div>
        </div>
      </section>

      {/* Competitive Edge Section */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-3xl md:text-4xl font-bold leading-tight">
                Maintain a Competitive Edge with{" "}
                <span className="text-[#6c5ce7]">LimeClicks</span>
              </h2>
              <p className="mt-6 text-gray-600 text-lg">
                Gain a competitive advantage with LimeClicks. Monitor
                competitors, receive updates on their actions and performance,
                and equip yourself with the tools and data to stay ahead in the
                game.
              </p>
              <div className="mt-8 space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-[#6c5ce7]/10 flex items-center justify-center">
                    <Bell className="w-5 h-5 text-[#6c5ce7]" />
                  </div>
                  <span className="text-lg font-medium">
                    Get alerts when their ranking changes
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-[#6c5ce7]/10 flex items-center justify-center">
                    <RefreshCw className="w-5 h-5 text-[#6c5ce7]" />
                  </div>
                  <span className="text-lg font-medium">
                    Daily competitor ranking updates
                  </span>
                </div>
              </div>
            </div>
            <div className="relative">
              <Image
                src="/images/screen.png"
                alt="Competitor Analysis"
                width={600}
                height={400}
                className="w-full h-auto rounded-xl shadow-2xl"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Brands & Agency Section */}
      <section className="py-20 bg-[#1a1a2e] text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div className="relative">
              <Image
                src="/images/dashboard2.png"
                alt="Dashboard"
                width={600}
                height={400}
                className="w-full h-auto rounded-xl shadow-2xl"
              />
            </div>
            <div>
              <h2 className="text-3xl md:text-4xl font-bold leading-tight">
                Lime Clicks for
                <br />
                <span className="text-[#6c5ce7]">Brands &amp; Agency</span>
              </h2>
              <p className="mt-6 text-gray-300 text-lg">
                LimeClicks provides solutions for both brands and agencies. Our
                agency-focused 100% white-label solution includes custom
                reporting templates.
              </p>
              <div className="mt-8 grid sm:grid-cols-2 gap-6">
                <div className="bg-white/10 rounded-xl p-6">
                  <Building2 className="w-8 h-8 text-[#6c5ce7] mb-3" />
                  <h3 className="font-bold text-xl mb-2">For Brands</h3>
                  <p className="text-gray-300">
                    Find quality traffic &amp; get daily ranking updates
                  </p>
                </div>
                <div className="bg-white/10 rounded-xl p-6">
                  <Users className="w-8 h-8 text-[#6c5ce7] mb-3" />
                  <h3 className="font-bold text-xl mb-2">For Agencies</h3>
                  <p className="text-gray-300">
                    White-labeled reports &amp; team access
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* About Section */}
      <section id="about" className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold">
              How Our <span className="text-[#6c5ce7]">Development</span> Works
            </h2>
            <p className="mt-4 text-gray-600 max-w-3xl mx-auto text-lg">
              At LimeClicks, our application is a testament to the synergy of
              our team and the clarity of our vision. Although we may be a
              compact team, our collective dedication spans years, as we&apos;ve
              collaborated to craft a tool that embodies our genuine passion.
              Allow us to share more about who we are.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
            <TeamCard
              name="Ammad Rafi"
              role="CEO"
              initials="AR"
              gradient="from-[#6c5ce7] to-[#a29bfe]"
              linkedin="https://www.linkedin.com/in/ammad-rafi-2a585b23/"
            />
            <TeamCard
              name="Muaaz Rafi"
              role="CTO"
              initials="MR"
              gradient="from-[#00b894] to-[#55efc4]"
            />
            <TeamCard
              name="Shahid Rasool"
              role="CMO"
              initials="SR"
              gradient="from-[#fdcb6e] to-[#f39c12]"
            />
            <TeamCard
              name="Ahmad Hayat"
              role="Technical Project Manager"
              initials="AH"
              gradient="from-[#e17055] to-[#fab1a0]"
              linkedin="https://www.linkedin.com/in/ahmad-hayat-11078497/"
            />
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <a
            href={SIGNUP}
            className="inline-flex items-center gap-2 bg-[#6c5ce7] hover:bg-[#5a4bd1] text-white px-10 py-4 rounded-lg font-semibold text-lg transition mb-16"
          >
            Try LimeClicks for Free <ArrowRight className="w-5 h-5" />
          </a>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <StatCard
              icon={<TrendingUp className="w-8 h-8" />}
              value="30.8k+"
              label="Happy Customers"
            />
            <StatCard
              icon={<FolderKanban className="w-8 h-8" />}
              value="102.3k"
              label="Project Added"
            />
            <StatCard
              icon={<ThumbsUp className="w-8 h-8" />}
              value="100%"
              label="Clients Satisfied"
            />
            <StatCard
              icon={<KeyRound className="w-8 h-8" />}
              value="15.5M+"
              label="Keywords Tracking"
            />
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold">
              Pricing Plans &amp; Packages
            </h2>
            <p className="mt-4 text-gray-600 max-w-2xl mx-auto">
              On the other hand we denounce with righteous indignation dislike
              men who are so beguiled and demoralized.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <PricingCard
              name="Basic"
              price="10"
              features={[
                "2 domains",
                "500 Keywords",
                "Multiple users",
                "White-labeld reports",
                "£5/extra domain",
                "£5/extra 100 keywords",
              ]}
            />
            <PricingCard
              name="Pro"
              price="30"
              popular
              features={[
                "10 domains",
                "1000 Keywords",
                "Multiple users",
                "White-labeld reports",
                "Priority support",
                "14 Days free Trial",
              ]}
            />
            <PricingCard
              name="Elite"
              price="60"
              features={[
                "50 Domains",
                "2000 Keywords",
                "Multiple Users",
                "White-labeld reports",
                "Priority support",
                "14 Days free Trial",
              ]}
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer id="contact" className="bg-[#1a1a2e] text-white pt-16 pb-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-3 gap-12">
            <div>
              <Image
                src="/images/logo.png"
                alt="LimeClicks"
                width={180}
                height={40}
                className="h-10 w-auto mb-6"
              />
              <p className="text-gray-400">
                Monitor your Google search rankings and stay ahead of the
                competition with LimeClicks.
              </p>
            </div>
            <div>
              <h3 className="font-bold text-lg mb-4">Quick Links</h3>
              <div className="space-y-3">
                <a
                  href="#features"
                  className="block text-gray-400 hover:text-white transition"
                >
                  Features
                </a>
                <a
                  href="#pricing"
                  className="block text-gray-400 hover:text-white transition"
                >
                  Pricing
                </a>
                <a
                  href={SIGNUP}
                  className="block text-gray-400 hover:text-white transition"
                >
                  Register
                </a>
                <a
                  href={SIGNIN}
                  className="block text-gray-400 hover:text-white transition"
                >
                  Login
                </a>
              </div>
            </div>
            <div>
              <h3 className="font-bold text-lg mb-4">Contact Us</h3>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <MapPin className="w-5 h-5 text-[#6c5ce7] mt-1 shrink-0" />
                  <span className="text-gray-400">
                    39 Freshwater Road,
                    <br />
                    Dagenham, England,
                    <br />
                    RM8 1SP
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <Phone className="w-5 h-5 text-[#6c5ce7] shrink-0" />
                  <a
                    href="tel:+447999936013"
                    className="text-gray-400 hover:text-white transition"
                  >
                    +44 799 993 6013
                  </a>
                </div>
                <div className="flex items-center gap-3">
                  <Mail className="w-5 h-5 text-[#6c5ce7] shrink-0" />
                  <a
                    href="mailto:support@limeclicks.com"
                    className="text-gray-400 hover:text-white transition"
                  >
                    support@limeclicks.com
                  </a>
                </div>
              </div>
            </div>
          </div>
          <div className="border-t border-white/10 mt-12 pt-8 text-center text-gray-500 text-sm">
            &copy; {new Date().getFullYear()} LimeClicks. All rights reserved.
          </div>
        </div>
      </footer>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-white rounded-xl p-8 shadow-sm hover:shadow-lg transition group">
      <div className="w-14 h-14 rounded-lg bg-[#6c5ce7]/10 flex items-center justify-center text-[#6c5ce7] mb-5 group-hover:bg-[#6c5ce7] group-hover:text-white transition">
        {icon}
      </div>
      <h3 className="font-bold text-xl mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  );
}

function StatCard({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
}) {
  return (
    <div className="text-center">
      <div className="w-16 h-16 rounded-full bg-[#6c5ce7]/10 flex items-center justify-center text-[#6c5ce7] mx-auto mb-4">
        {icon}
      </div>
      <div className="text-3xl md:text-4xl font-bold text-[#6c5ce7]">
        {value}
      </div>
      <div className="text-gray-600 mt-1">{label}</div>
    </div>
  );
}

function TeamCard({
  name,
  role,
  initials,
  gradient,
  linkedin,
}: {
  name: string;
  role: string;
  initials: string;
  gradient: string;
  linkedin?: string;
}) {
  return (
    <div className="bg-white rounded-2xl p-8 shadow-sm hover:shadow-xl transition text-center group">
      <div
        className={`w-24 h-24 rounded-full bg-gradient-to-br ${gradient} flex items-center justify-center mx-auto mb-5 text-white text-2xl font-bold shadow-lg group-hover:scale-110 transition`}
      >
        {initials}
      </div>
      <h3 className="font-bold text-xl">{name}</h3>
      <p className="text-[#6c5ce7] font-medium mt-1">{role}</p>
      {linkedin && (
        <a
          href={linkedin}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-[#0077b5]/10 text-[#0077b5] hover:bg-[#0077b5] hover:text-white transition mt-3"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
        </a>
      )}
    </div>
  );
}

function PricingCard({
  name,
  price,
  features,
  popular,
}: {
  name: string;
  price: string;
  features: string[];
  popular?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl p-8 ${popular ? "bg-[#6c5ce7] text-white ring-4 ring-[#6c5ce7]/30 scale-105" : "bg-white border border-gray-200"} shadow-lg relative`}
    >
      {popular && (
        <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-yellow-400 text-black px-4 py-1 rounded-full text-sm font-bold">
          Most Popular
        </div>
      )}
      <h3 className="text-xl font-bold">{name}</h3>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-4xl font-bold">£{price}</span>
        <span className={popular ? "text-white/70" : "text-gray-500"}>
          / month
        </span>
      </div>
      <ul className="mt-8 space-y-3">
        {features.map((f) => (
          <li key={f} className="flex items-center gap-3">
            <Check
              className={`w-5 h-5 shrink-0 ${popular ? "text-white" : "text-[#6c5ce7]"}`}
            />
            <span>{f}</span>
          </li>
        ))}
      </ul>
      <a
        href={SIGNUP}
        className={`mt-8 block text-center py-3 rounded-lg font-semibold transition ${popular ? "bg-white text-[#6c5ce7] hover:bg-gray-100" : "bg-[#6c5ce7] text-white hover:bg-[#5a4bd1]"}`}
      >
        Select Plan
      </a>
    </div>
  );
}
