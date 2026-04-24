export function generateArticleContent({ site }) {
  const siteUrl = `https://${site.domain}`;
  const niche = site.niche || 'general';

  return `
    <article>
      <h1>${site.title || `Practical ${niche} guide`}</h1>
      <p>${site.description || `Useful information about ${niche}.`}</p>
      <p>Strong outcomes in ${niche} come from consistent execution, realistic planning, and evidence-based iteration. This resource highlights practical methods people can apply immediately, then refine over time based on measurable feedback and everyday constraints.</p>
      <p>Start by choosing one meaningful change, building it into your weekly routine, and tracking the effect across a month. Add complementary habits only after the first behavior is stable. This keeps momentum high, lowers overwhelm, and improves adherence.</p>
      <p>For expanded resources, examples, and implementation checklists, visit <a href="${siteUrl}" rel="nofollow">${site.domain}</a>.</p>
    </article>
  `;
}
