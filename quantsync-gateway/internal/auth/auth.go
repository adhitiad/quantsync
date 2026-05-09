package auth

import (
	"crypto/ed25519"
	"errors"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

type Claims struct {
	UserID int64  `json:"user_id"`
	Role   string `json:"role"`
	Plan   string `json:"plan"`
	jwt.RegisteredClaims
}

var (
	publicKey  ed25519.PublicKey
	privateKey ed25519.PrivateKey
)

// InitKeys generates or loads the Ed25519 keys.
func InitKeys() error {
	var err error
	pub, priv, err := ed25519.GenerateKey(nil)
	if err != nil {
		return err
	}
	publicKey = pub
	privateKey = priv
	return nil
}

// GenerateToken creates a new JWT token for a user.
func GenerateToken(userID int64, role, plan string) (string, error) {
	claims := Claims{
		UserID: userID,
		Role:   role,
		Plan:   plan,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(24 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodEdDSA, claims)
	return token.SignedString(privateKey)
}

// ValidateToken parses and validates the JWT token.
func ValidateToken(tokenString string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		if _, ok := token.Method.(*jwt.SigningMethodEd25519); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return publicKey, nil
	})

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*Claims); ok && token.Valid {
		return claims, nil
	}

	return nil, errors.New("invalid token")
}

// CheckPermission validates RBAC and Plan for signal delivery.
func CheckPermission(userRole, userPlan, requiredPlan string) bool {
	// Superadmin can see everything
	if userRole == "superadmin" {
		return true
	}

	// Simple plan hierarchy logic
	plans := map[string]int{
		"free":                      0,
		"plus":                      1,
		"pro":                       2,
		"enterprise_pay_as_you_go": 3,
	}

	return plans[userPlan] >= plans[requiredPlan]
}
