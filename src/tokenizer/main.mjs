import llamaTokenizer from 'llama-tokenizer-js'
import readline from 'readline'

function main(args) {
    if (args[0] == '--run-tests') {
        if (!llamaTokenizer.runTests()) {
            process.exit(1)
        }
        return
    }

    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
        terminal: false
    });

    rl.on('line', (input) => {
        console.log(llamaTokenizer.encode(input).length)
    });
}

if (import.meta.url === 'file://' + new URL(import.meta.url).pathname) {
    const args = process.argv.slice(2);
    main(args);
}