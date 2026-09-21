/** No preselected attestation or license. A real user supplies source evidence. */
export function preparationDialog({source,file,esc,b}) {
  return {body:`<p><strong>${esc(source.name)}</strong> is already local. No download or provider login is needed.</p>
    <ol class="preparation-steps"><li>Confirm the actual source and retained rights.</li><li>Check a separate copy in Blender, including package-local dependencies.</li><li>Review production use and collections, then import a new scene change.</li></ol>
    <p>The shared catalog copy can be reused across productions. Preparation is bounded to 500 MiB; temporary inspection copies also use disk space. Originals and existing scenes stay untouched.</p>
    <p>Selected member: <code>${esc(file)}</code></p>
    <div class="preparation-fields">
    <label>Original source page<input id="prepare-source-url" type="url" maxlength="2000" placeholder="https://…" required></label>
    <label>Creator / attribution<input id="prepare-author" maxlength="2000" required></label>
    <label>Actual recorded license<select id="prepare-license" required><option value="">Choose the verified license</option><option value="CC0-1.0">CC0 1.0</option><option value="CC-BY-4.0">CC BY 4.0</option><option value="CC-BY-3.0">CC BY 3.0</option></select></label>
    <label>Retained license / terms reference<input id="prepare-license-url" type="url" maxlength="2000" placeholder="https://…" required></label>
    </div><p class="note">Unknown or custom rights need the existing specialist review. Do not choose a license merely to enable import. These source records do not clear third-party rights or approve a production.</p>
    <label class="preparation-confirm"><input id="prepare-confirm" type="checkbox"> I verified this zero-cost source, creator and license against the retained evidence. Save these claims with this exact package version.</label>`,
    buttons:b('Verify & prepare','source-prepare',{id:source.id,version:source.version,file},'primary')};
}
