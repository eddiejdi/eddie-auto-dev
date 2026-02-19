
// CPU intensive tasks
function fibonacci(n) {
    if (n <= 1) return n;
    let a = 0, b = 1;
    for (let i = 2; i <= n; i++) {
        [a, b] = [b, a + b];
    }
    return b;
}

function isPrime(n) {
    if (n < 2) return false;
    for (let i = 2; i <= Math.sqrt(n); i++) {
        if (n % i === 0) return false;
    }
    return true;
}

// Heavy computation
for (let i = 0; i < 5000; i++) fibonacci(i);
const primes = [];
for (let i = 2; i < 50000; i++) {
    if (isPrime(i)) primes.push(i);
}

// Sorting benchmark
const arr = Array.from({length: 100000}, () => Math.random());
arr.sort((a, b) => a - b);

console.log("Fibonacci: 5000, Primes: " + primes.length + ", Sort: 100000");
