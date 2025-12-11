# windows-x64-shellcode-pipeline

A Dockerized build pipeline for custom Windows x64 shellcode, including a custom encoder stub and fully automated payload preparation.

## Background

I highly recommend trying to build Windows shellcode from scratch at least once. It's a checkpoint of understanding malware development and Windows internals. But authoring shellcode by writing assembly directly is something I wouldn't wish on my worst ops.

Inspired by @hasherezade's excellent paper [From a C project, through assembly, to shellcode](https://raw.githubusercontent.com/hasherezade/masm_shc/master/docs/FromaCprojectthroughassemblytoshellcode.pdf), this is a full build pipeline for customized x64 Windows shellcode that allows users to author payloads in C rather than assembly. Writing shellcode directly in assembly is time consuming, tedious, and error prone. Compiling a C program tailored for position-independent execution and subsequentally extracting the code from that PE is a much better option, which is what her paper covers. 

Her paper details how to perform the process entirely within the Visual Studio dev environment, which usually means developing within Windows. I wanted to port this process over to a Dockerized build pipeline that supports the entire process and cross-compiles the source into the final product. This project also implements the automated post-processing that her paper mentions. 

### Features

- Allows you to author the final payloads as modular, ergonomic C source rather than error-prone assembly.
- Builds the shellcode in stages: first as the assembly of a scaffolded PE built for PIC execution, then with automated Python post-processing to clean the resulting assembly, and finally as a PIC `.bin` file ready for execution
- Handles potential stack alignment errors by implementing Matt Graeber's tried-and-true [AlignRSP stub](https://github.com/mattifestation/PIC_Bindshell/blob/master/PIC_Bindshell/AdjustStack.asm#L24)  
- Includes an example of a simple encoder/decoder stub (single byte XOR) to show the process of generating polymorphic shellcode that is built in an encoded state and decoded at execution (think Shikata Ga Nai).

The point here is to demonstrate the build pipeline, not necessarily provide you with field-grade shellcode.

## Building

The Makefile supports building the shellcode to each individual phase for testing and evaluation. Calling `make` with no arguments will run the entire build pipeline all the way to the final shellcode `.bin` file.

You may encounter warnings when running make, but the pipeline will still work:

```
λ make
docker build -t shellcode-build-pipeline:latest .

...[snip]...

python3 tools/handle_asm.py clean build/c-shellcode.s build/c-shellcode_cleaned.asm
[+] Cleaned assembly written to build/c-shellcode_cleaned.asm
x86_64-w64-mingw32-gcc -c -x assembler-with-cpp -o 

...[snip]...

python3 tools/handle_asm.py extract build/c-shellcode.exe build/c-shellcode_64_encoded.bin
[*] Entry point RVA: 0x1000
[*] .text section: VirtualAddr=0x1000, RawPtr=0x400, RawSize=0x400
[*] Entry point offset in .text: 0x0
[+] Raw payload length: 892 bytes
[+] Final shellcode (stub + encoded payload): 922 bytes

/* ================== C SHELLCODE ARRAY ================== */
unsigned char shellcode_64[] = {
    0x48, 0x8d, /*... snip */
};
unsigned int shellcode_64_len = 922;
```

This prints the shellcode to the terminal formatted similarly to how `msfvenom` would output it and also writes the `.bin` file to the build dir.

<img width="635" height="181" alt="image" src="https://github.com/user-attachments/assets/1809a8d3-15e9-4c30-8d2e-f3beb8759013" />

## Custom Payloads

The source comes with an example payload file (`src/payload_msgbox.c`) which should give you a good starting point on how to develop a custom payload. The other source files handle the rest of the work required to bootstrap and execute position-independent code, including the runtime and calling the shellcode entrypoint after aligning the stack to the 16-byte boundary. With that in mind, to write a custom payload, you need to:

- Write a new file that implements the payload of your shellcode in C
- Add the new payload to the end of the `shellcode.c` orchestrator:

```
...
#include "runtime.c"
// #include "payload_msgbox.c"
#include "your_payload_source_here.c"
```

The shellcode entrypoint is `payload_main(SC_ENV *env)`. The SC_ENV struct is initialized by `runtime.c` after locating the PEB, resolving the base of required modules, and resolving API addresses. This is effectively a miniature loader that reconstructs enough of an IAT for position-independent execution (shoutout to @hasherezade and her paper, which covers all of this and provided excellent implementation of how to do the bootstrapping). 

```c
void payload_main(SC_ENV *env) {
    if (!env->pLoadLibraryA || !env->pGetProcAddress) {
        return;
    }

    // Stack strings so we can store our strings inline of the shellcode rather than in an external section
    char user32_dll_name[] = { 'u','s','e','r','3','2','.','d','l','l', 0 };
    char message_box_name[] = { 'M','e','s','s','a','g','e','B','o','x','W', 0 };

    wchar_t msg_content[] = { 'H','e','l','l','o',' ','W','o','r','l','d','!', 0 };
    wchar_t msg_title[]   = { 'D','e','m','o','!', 0 };

    HMODULE u32 = env->pLoadLibraryA(user32_dll_name);
    if (!u32) {
        return;
    }

    int (WINAPI *pMessageBoxW)(
        HWND,
        LPCWSTR,
        LPCWSTR,
        UINT
    ) = (int (WINAPI*)(HWND, LPCWSTR, LPCWSTR, UINT))
        env->pGetProcAddress(u32, message_box_name);

    if (!pMessageBoxW) {
        return;
    }

    pMessageBoxW(0, msg_content, msg_title, MB_OK);
}
```

You would need to implement the C code to perform the actual payload within the entrypoint function, assemble the stack strings to call the APIs, define custom implementation of the dynamically loaded APIs, and then execute the actual payload. Be careful: even though the build pipeline handles most of the transformation to get this payload into PIC-ready form, certain C patterns will not work well as shellcode. In general, the guidelines are:

- no global data, 
- no absolute addressing, 
- no reliance on compiler-inserted CRT initialization.
- try not to use JMP tables if you can help it

## Custom Encoder

The build pipeline includes a simple, naive example of obfuscating shellcode. The example implements the encoder during the build process and the decoder stub that reverses the encoding schema at runtime. The example is a single byte XOR, which probably won't make it past a basic EDR tbh, but that's not the point.

Implementing a more sophisticated, custom encoder is a matter of building out the two corresponding functions in `encoder.py`: the encoding routine (Pyton) and the decoder stub (implemented directly in Assembly and appended with Python in the example). The important thing is that your implementation must match, of course, so adding a new kind of encoding/encrypting schema is a matter of implementing the encoder as a Python function against the payload bytes and writing an assembly stub that unwinds the encoding.

## Credits

- @hasherezade for the excellent paper and implementation of bootstrapping API calls from shellcode
- Matt Graeber (@mattifestation) for the AlignRSP stub
- Maldev Academy for the inspiration

