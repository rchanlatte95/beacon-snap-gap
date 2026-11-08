import { Fragment, useContext } from 'react'
import { SOURCE_REGISTER_URL, SourcesContext } from './sources'

export function SourceLinks({ ids }: { readonly ids: readonly string[] }) {
  const sources = useContext(SourcesContext)
  return (
    <p className="sources source-links">
      Sources:{' '}
      {ids.map((id, index) => {
        const source = sources.find((entry) => entry.id === id)
        return (
          <Fragment key={id}>
            {index > 0 && ' · '}
            {source ? (
              <a
                href={source.url}
                target="_blank"
                rel="noreferrer"
                title={`${source.publisher}. ${source.period}. ${id}`}
              >
                {source.label}
              </a>
            ) : (
              <span>{id} (source not registered)</span>
            )}
          </Fragment>
        )
      })}
    </p>
  )
}

export function DataSources({
  povertyCut,
  lendingCut,
  lendingPart,
  minPopulation,
  transportCut,
}: {
  readonly povertyCut: string
  readonly lendingCut: number
  /** For example "lowest quarter". */
  readonly lendingPart: string
  readonly minPopulation: number
  readonly transportCut: string
}) {
  const sources = useContext(SourcesContext)
  return (
    <section className="data-sources shell" aria-label="Data sources and methods">
      <details className="source-register">
        <summary>Data sources and methods</summary>
        <div className="source-register-body">
          <p>
            Values come from saved source snapshots, not a live feed. Dates differ by source.
            <a href={SOURCE_REGISTER_URL} target="_blank" rel="noreferrer">
              {' '}
              Read the source register and retrieval notes.
            </a>
          </p>
          <h2>How gaps are defined</h2>
          <ul className="source-methods">
            <li>
              Food desert: poverty at or above {povertyCut}% and the USDA low-income, low-access
              driving-distance flag.
            </li>
            <li>
              Few business loans: a food desert with at least{' '}
              {minPopulation.toLocaleString('en-US')} residents and at most {lendingCut.toFixed(4)}{' '}
              SBA loans per 1,000 residents, the {lendingPart} of populated neighborhoods. This
              describes recorded lending, not a measured need for capital.
            </li>
            <li>
              Transport gap: a food desert where at least {transportCut}% of households have no
              vehicle.
            </li>
            <li>The three cuts above follow the gap rules chosen above the map.</li>
            <li>
              Pantry distance: straight-line miles from each populated 2020 census block to the
              nearest listed Second Harvest site. A neighborhood is within the chosen distance when
              any of its populated blocks is. This is not road distance, and it does not show
              opening hours or capacity.
            </li>
          </ul>
          <div className="source-grid">
            {sources.map((source) => (
              <article
                className="source-entry"
                key={source.id}
                data-testid={`source-entry-${source.id}`}
              >
                <h3>
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.label}
                  </a>
                </h3>
                <p className="source-publisher">{source.publisher}</p>
                <p className="source-period">
                  {source.period} · {source.id}
                </p>
                <p>{source.method}</p>
                <p className="source-limits">{source.limits}</p>
              </article>
            ))}
          </div>
        </div>
      </details>
    </section>
  )
}
