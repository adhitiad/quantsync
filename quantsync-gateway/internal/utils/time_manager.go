package utils

import (
	"time"
)

// Market zones
const (
	ZoneJakarta = "Asia/Jakarta"
	ZoneLondon  = "Europe/London"
	ZoneNewYork = "America/New_York"
)

// TripleTime holds time in three major financial zones
type TripleTime struct {
	Jakarta time.Time
	London  time.Time
	NewYork time.Time
	UTC     time.Time
}

// GetTripleTime returns the current time in Jakarta, London, and New York
func GetTripleTime() TripleTime {
	utc := time.Now().UTC()

	locJKT, _ := time.LoadLocation(ZoneJakarta)
	locLDN, _ := time.LoadLocation(ZoneLondon)
	locNY, _ := time.LoadLocation(ZoneNewYork)

	return TripleTime{
		Jakarta: utc.In(locJKT),
		London:  utc.In(locLDN),
		NewYork: utc.In(locNY),
		UTC:     utc,
	}
}

// IsMarketOpen checks if a specific session is open based on hour ranges (simplified)
func (t TripleTime) IsNYOpen() bool {
	h := t.NewYork.Hour()
	return h >= 8 && h < 17 // 08:00 - 17:00 EST
}

func (t TripleTime) IsLondonOpen() bool {
	h := t.London.Hour()
	return h >= 8 && h < 16 // 08:00 - 16:00 GMT/BST
}

func (t TripleTime) IsOverlap() bool {
	return t.IsNYOpen() && t.IsLondonOpen()
}
