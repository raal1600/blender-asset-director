/** One explicit confirmation; no default answer or invented license metadata. */
export function preparationDialog({source,file,projectName,esc,b}) {
  return {body:`<p class="preparation-asset"><strong>${esc(source.name)}</strong></p>
    <p>Director will check a separate copy and prepare this asset for your library. No download or purchase. ${projectName?'It will then add the verified asset to your draft in <strong>'+esc(projectName)+'</strong>. Originals and saved checkpoints stay unchanged.':'Your originals and scene stay unchanged.'}</p>
    <label class="preparation-confirm"><input id="prepare-confirm" type="checkbox"> <span>I confirm I have the right to use and adapt this asset ${projectName?'in '+esc(projectName):'in my productions'} and will follow its terms, including any required credits.</span></label>
    <p class="note">This records your confirmation—not a verified license. It covers this version only, not future files, raw redistribution or model training.</p>
    <details class="preparation-details"><summary>What will be prepared?</summary><p>Selected file: <code>${esc(file)}</code></p><p>At most 500 MiB. A separate Blender copy checks package-local dependencies. Existing reviewed rights are preserved. Preparation does not import objects or approve a scene.</p></details>`,
    buttons:b(projectName?'Confirm & add to scene':'Confirm & prepare','source-prepare',{id:source.id,version:source.version,file},'primary',true)};
}
