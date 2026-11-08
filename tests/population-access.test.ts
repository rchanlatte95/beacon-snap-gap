import { describe, expect, it } from 'vitest'
import { populationAccess, populationAccessText } from '../src/map/populationAccess'

function population(shares: number[], pop2020 = 1000) {
  return {
    pop2020,
    nearest_block_miles: 0.1,
    reach_share: Array.from({ length: 41 }, (_, index) => shares[index] ?? 1),
  }
}

describe('population coverage access heuristic', () => {
  it('uses the radius covering 80% instead of the closest residents or the center', () => {
    const access = populationAccess(population([0, 0.1, 0.2, 0.4, 0.5, 0.6, 0.79, 0.81]))
    expect(access).toEqual({
      status: 'estimated',
      minutes: 10.5,
    })
    expect(populationAccessText(access)).toBe('11 min')
  })

  it('includes exactly 80% and shows a single time using the covering radius', () => {
    const access = populationAccess(population([0, 0.4, 0.8]))
    expect(access).toEqual({
      status: 'estimated',
      minutes: 3,
    })
    expect(populationAccessText(access)).toBe('3 min')
  })

  it('shows beyond the data limit without inventing a percentile distance or zero minutes', () => {
    const access = populationAccess(population(Array.from({ length: 41 }, () => 0.79)))
    expect(access).toEqual({ status: 'beyond', minutes: 60 })
    expect(populationAccessText(access)).toBe('Over 60 min')
  })

  it('keeps missing populations, missing locations and invalid coverage separate from measured zero', () => {
    for (const tract of [
      population([0], 0),
      { ...population([0]), nearest_block_miles: null },
      { ...population([0]), reach_share: [] },
      population([0, 0.5, 0.4]),
      population([0, 1.1]),
    ]) {
      expect(populationAccess(tract)).toEqual({ status: 'unavailable' })
    }
    expect(populationAccessText({ status: 'unavailable' })).toBe('No data')
    expect(populationAccessText(populationAccess(population([0, 0.8])))).toBe('2 min')
  })
})
