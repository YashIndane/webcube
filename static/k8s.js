const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

function speak(msg){

    const speech = new SpeechSynthesisUtterance();
    speech.text = msg;
    speech.volume = 1;
    speech.rate = 1;
    speech.pitch = 1;
    window.speechSynthesis.speak(speech);
}

const DEF_DELAY = 1000;
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms || DEF_DELAY));
}

//await sleep(100);

(async()=>{

