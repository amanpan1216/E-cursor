/**
 * Intelligent hCaptcha Fallback Selector
 * Selects the best fallback method based on context and previous attempts
 */

class HCaptchaFallbackSelector {
    constructor() {
        this.methodStats = {};
        this.attemptHistory = [];
        this.contextData = {};
        this.successRates = {};
        
        // Initialize method stats
        const methods = [
            'jwtTokenMethod',
            'signatureTokenMethod',
            'timestampTokenMethod',
            'hybridTokenMethod',
            'encryptedTokenMethod',
            'randomTokenMethod',
            'behaviorAnalysisMethod',
            'deviceFingerprintMethod',
            'contextualTokenMethod',
            'adaptiveTokenMethod'
        ];

        methods.forEach(method => {
            this.methodStats[method] = {
                attempts: 0,
                successes: 0,
                failures: 0,
                avgTime: 0,
                lastUsed: null
            };
            this.successRates[method] = 0;
        });
    }

    /**
     * Record an attempt result
     */
    recordAttempt(methodName, success, duration = 0) {
        if (!this.methodStats[methodName]) {
            this.methodStats[methodName] = {
                attempts: 0,
                successes: 0,
                failures: 0,
                avgTime: 0,
                lastUsed: null
            };
        }

        const stats = this.methodStats[methodName];
        stats.attempts++;
        stats.lastUsed = new Date();

        if (success) {
            stats.successes++;
        } else {
            stats.failures++;
        }

        // Update average time
        stats.avgTime = (stats.avgTime * (stats.attempts - 1) + duration) / stats.attempts;

        // Update success rate
        this.successRates[methodName] = stats.attempts > 0 
            ? (stats.successes / stats.attempts) * 100 
            : 0;

        this.attemptHistory.push({
            method: methodName,
            success,
            duration,
            timestamp: new Date()
        });
    }

    /**
     * Get the best method based on success rate and speed
     */
    getBestMethod() {
        let bestMethod = null;
        let bestScore = -1;

        for (const [method, rate] of Object.entries(this.successRates)) {
            const stats = this.methodStats[method];
            
            // Score = success rate (70%) + speed bonus (30%)
            // Faster methods get higher scores
            const speedBonus = Math.max(0, 100 - (stats.avgTime / 10));
            const score = (rate * 0.7) + (speedBonus * 0.3);

            if (score > bestScore) {
                bestScore = score;
                bestMethod = method;
            }
        }

        return bestMethod || 'jwtTokenMethod';
    }

    /**
     * Get the next method to try (intelligent selection)
     */
    getNextMethod(previousMethods = []) {
        // Filter out previously tried methods
        const availableMethods = Object.keys(this.methodStats).filter(
            method => !previousMethods.includes(method)
        );

        if (availableMethods.length === 0) {
            // All methods tried, return the best one
            return this.getBestMethod();
        }

        // Sort by success rate (descending)
        availableMethods.sort((a, b) => {
            const rateA = this.successRates[a] || 0;
            const rateB = this.successRates[b] || 0;
            
            // If both have same success rate, prefer faster one
            if (Math.abs(rateA - rateB) < 5) {
                const timeA = this.methodStats[a].avgTime || Infinity;
                const timeB = this.methodStats[b].avgTime || Infinity;
                return timeA - timeB;
            }
            
            return rateB - rateA;
        });

        return availableMethods[0];
    }

    /**
     * Get method recommendations based on context
     */
    getRecommendations(context = {}) {
        const recommendations = [];

        // Analyze context
        const isMobileUser = context.userAgent && context.userAgent.includes('Mobile');
        const isHighLatency = context.latency && context.latency > 500;
        const isPreviousFail = context.previousFailure;

        // Recommend methods based on context
        if (isMobileUser) {
            // Mobile users: prefer faster methods
            recommendations.push('randomTokenMethod');
            recommendations.push('timestampTokenMethod');
            recommendations.push('jwtTokenMethod');
        } else if (isHighLatency) {
            // High latency: prefer simple methods
            recommendations.push('randomTokenMethod');
            recommendations.push('signatureTokenMethod');
        } else if (isPreviousFail) {
            // Previous failure: try different approach
            recommendations.push('hybridTokenMethod');
            recommendations.push('encryptedTokenMethod');
            recommendations.push('adaptiveTokenMethod');
        } else {
            // Default: try best performing methods first
            const sortedMethods = Object.keys(this.successRates).sort(
                (a, b) => (this.successRates[b] || 0) - (this.successRates[a] || 0)
            );
            recommendations.push(...sortedMethods.slice(0, 5));
        }

        return recommendations;
    }

    /**
     * Get statistics about method performance
     */
    getStatistics() {
        const stats = {};

        for (const [method, data] of Object.entries(this.methodStats)) {
            stats[method] = {
                attempts: data.attempts,
                successes: data.successes,
                failures: data.failures,
                successRate: this.successRates[method].toFixed(2) + '%',
                avgTime: data.avgTime.toFixed(2) + 'ms',
                lastUsed: data.lastUsed ? data.lastUsed.toISOString() : 'Never'
            };
        }

        return {
            totalAttempts: this.attemptHistory.length,
            totalSuccesses: this.attemptHistory.filter(a => a.success).length,
            totalFailures: this.attemptHistory.filter(a => !a.success).length,
            overallSuccessRate: (
                (this.attemptHistory.filter(a => a.success).length / this.attemptHistory.length) * 100
            ).toFixed(2) + '%',
            bestMethod: this.getBestMethod(),
            methodStats: stats
        };
    }

    /**
     * Reset statistics (for new session)
     */
    reset() {
        const methods = Object.keys(this.methodStats);
        methods.forEach(method => {
            this.methodStats[method] = {
                attempts: 0,
                successes: 0,
                failures: 0,
                avgTime: 0,
                lastUsed: null
            };
            this.successRates[method] = 0;
        });
        this.attemptHistory = [];
        this.contextData = {};
    }

    /**
     * Set context data for better recommendations
     */
    setContext(contextData) {
        this.contextData = { ...this.contextData, ...contextData };
    }

    /**
     * Get context data
     */
    getContext() {
        return this.contextData;
    }

    /**
     * Predict success probability for a method
     */
    predictSuccess(methodName) {
        if (!this.methodStats[methodName]) {
            return 50; // Default 50% for unknown methods
        }

        const stats = this.methodStats[methodName];
        if (stats.attempts === 0) {
            return 50;
        }

        return (stats.successes / stats.attempts) * 100;
    }

    /**
     * Get method performance ranking
     */
    getRanking() {
        const ranking = Object.entries(this.methodStats)
            .map(([method, stats]) => ({
                method,
                successRate: this.successRates[method] || 0,
                attempts: stats.attempts,
                avgTime: stats.avgTime
            }))
            .sort((a, b) => b.successRate - a.successRate);

        return ranking;
    }
}

module.exports = HCaptchaFallbackSelector;
