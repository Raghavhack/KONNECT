const express = require("express");
const router = express.Router();

const PLANS = {
  free: {
    id: "free",
    name: "Starter",
    price: 0,
    features: ["Up to 3 data sources", "Daily knowledge graph sync", "Standard PCST retrieval", "Community support"],
  },
  pro: {
    id: "pro",
    name: "Pro Researcher",
    price: 29,
    features: [
      "Unlimited data sources (OneDrive, Google Drive, Notion, Slack)",
      "Real-time incremental ROLAND GRU re-embedding",
      "Priority PCST subgraph retrieval",
      "Redis semantic caching",
      "Custom Neo4j GDS tuning",
    ],
  },
  enterprise: {
    id: "enterprise",
    name: "Enterprise",
    price: 99,
    features: [
      "Dedicated Neo4j instance",
      "Custom LLM API endpoints (Anthropic/OpenAI/Gemini/Ollama)",
      "Role-based access control & SOC-2 compliance",
      "SLA guarantee",
    ],
  },
};

/**
 * GET /api/billing/plans
 */
router.get("/plans", (req, res) => {
  res.json({ success: true, plans: Object.values(PLANS) });
});

/**
 * GET /api/billing/status
 */
router.get("/status", (req, res) => {
  res.json({
    success: true,
    plan: "pro",
    status: "active",
    currentPeriodEnd: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  });
});

/**
 * POST /api/billing/checkout
 */
router.post("/checkout", (req, res) => {
  const { planId = "pro", successUrl, cancelUrl } = req.body;
  const plan = PLANS[planId] || PLANS.pro;

  // In production: const session = await stripe.checkout.sessions.create(...)
  const checkoutUrl =
    successUrl ||
    `http://localhost:5173/live-demo?billing=success&plan=${plan.id}`;

  res.json({
    success: true,
    checkoutUrl,
    sessionId: `cs_test_${Date.now()}`,
    plan,
  });
});

/**
 * POST /api/billing/webhook
 * Handles Stripe webhook events (checkout.session.completed, etc.)
 */
router.post("/webhook", express.raw({ type: "application/json" }), (req, res) => {
  const event = req.body;
  console.log(`[Billing Webhook] Received Stripe event: ${event?.type || "checkout.session.completed"}`);

  // Acknowledge receipt
  res.json({ received: true });
});

module.exports = router;

