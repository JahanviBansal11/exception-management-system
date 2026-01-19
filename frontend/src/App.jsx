// import { useState } from 'react'
// import reactLogo from './assets/react.svg'
// import viteLogo from '/vite.svg'
// import './App.css'

// function App() {
//   const [count, setCount] = useState(0)

//   return (
//     <>
//       <div>
//         <a href="https://vite.dev" target="_blank">
//           <img src={viteLogo} className="logo" alt="Vite logo" />
//         </a>
//         <a href="https://react.dev" target="_blank">
//           <img src={reactLogo} className="logo react" alt="React logo" />
//         </a>
//       </div>
//       <h1>Vite + React</h1>
//       <div className="card">
//         <button onClick={() => setCount((count) => count + 1)}>
//           count is {count}
//         </button>
//         <p>
//           Edit <code>src/App.jsx</code> and save to test HMR
//         </p>
//       </div>
//       <p className="read-the-docs">
//         Click on the Vite and React logos to learn more
//       </p>
//     </>
//   )
// }

// export default App


////===================================================
////connection test code
import { useEffect, useState } from 'react'
import axios from 'axios'

function App() {
  const [status, setStatus] = useState("Checking connection...")

  useEffect(() => {
    // We point Axios to your Django server URL
    axios.get('http://127.0.0.1:8000/')
      .then(response => {
        setStatus("Success! The Frontend is talking to the Backend.")
      })
      .catch(error => {
        setStatus("Connection Failed. Make sure Django is running!")
        console.error("Error details:", error)
      })
  }, [])

  return (
    <div style={{ textAlign: 'center', marginTop: '50px' }}>
      <h1>GRC Project</h1>
      <div style={{ 
        padding: '20px', 
        border: '1px solid #ccc', 
        display: 'inline-block',
        color: status.includes("Success") ? 'green' : 'red' 
      }}>
        {status}
      </div>
    </div>
  )
}

export default App