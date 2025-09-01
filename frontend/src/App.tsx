import { useState } from "react";
import Input from "./components/input";

import { useTheme } from "./providers/ThemeProvider";
function App() {
  const { theme, colors } = useTheme();

  return (
    <div className="bg-[{colors.background}]">
      <Input />
      <p>this browser uses {theme} theme</p>
      <p>the colors are</p>
      <p>docker refresh works! test #6</p>
    </div>
  );
}

export default App;
