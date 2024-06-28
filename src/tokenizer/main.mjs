import llamaTokenizer from 'llama-tokenizer-js';
import llama3Tokenizer from 'llama3-tokenizer-js';
import readline from 'readline';

function main(args) {
    if (args.includes('--run-tests')) {
        llama3Tokenizer.runTests();

        if (!llamaTokenizer.runTests()) {
            process.exit(1)
        }

        return;
    }

    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
        terminal: false
    });

    const isLlama2 = args.includes('--llama2');
    rl.on('line', (input) => {
        if (isLlama2) {
            console.log(llamaTokenizer.encode(input).length);
            return;
        } 

        console.log(llama3Tokenizer.encode(input).length);
    });
}

if (import.meta.url === 'file://' + new URL(import.meta.url).pathname) {
    const args = process.argv.slice(2);
    main(args);
}