import { Mail } from "lucide-react";

export default function Input() {
  return (
    <div className="flex items-center">
      <div className="flex items-center justify-center px-2">
        <Mail />
      </div>

      <input
        type="text"
        id="input-group-1"
        className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        placeholder="name@flowbite.com"
      />
    </div>
  );
}
