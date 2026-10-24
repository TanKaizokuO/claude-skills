import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

// Factories rebind on session changes; ask once per interactive process, not per bind.
let prompted = false;

export default function startupModelRecommendation(pi: ExtensionAPI): void {
	pi.on("session_start", (_event, ctx) => {
		if (prompted || ctx.mode !== "tui" || !ctx.hasUI || ctx.agent.kind !== "main") return;
		prompted = true;

		// session_start handlers have a 30s budget that cancels their UI; ask from a managed timer instead.
		ctx.setTimeout(async () => {
			const job = (await ctx.ui.input(
				"What job are you going to do?",
				"Describe the task for a model recommendation. Esc skips this step.",
			))?.trim();
			if (!job) return;

			pi.sendUserMessage(
				[
					"Run the suggest-model skill. First read skill://suggest-model and follow its instructions, including fetching current 5-hour and weekly subscription usage.",
					"Recommend a model for the job below. Do not perform the job or switch models. Stop after the recommendation and wait for the user.",
					`Job:\n${job}`,
				].join("\n\n"),
				{ attribution: "agent" },
			);
		}, 0);
	});
}
